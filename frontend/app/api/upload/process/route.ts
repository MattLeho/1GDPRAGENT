import { NextResponse, NextRequest } from 'next/server';
import { pool } from '@/lib/db';
import { readFile } from 'fs/promises';
import { GoogleGenAI } from '@google/genai';
import { getAICredential } from '@/lib/ai-credentials';
import { getWorkflowModelPreference } from '@/lib/model-preferences';
import { replaceArtifactsForFile } from '@/lib/data-artifacts';

const DEFAULT_PROCESS_DELAY_MS = 750;
const DEFAULT_RATE_LIMIT_DELAY_MS = 10000;

function getProcessDelayMs(): number {
    const configured = Number(process.env.UPLOAD_PROCESS_DELAY_MS);
    if (!Number.isFinite(configured)) {
        return DEFAULT_PROCESS_DELAY_MS;
    }

    return Math.min(Math.max(configured, 0), 60000);
}

function getRateLimitDelayMs(): number {
    const configured = Number(process.env.UPLOAD_SCAN_RATE_LIMIT_DELAY_MS);
    if (!Number.isFinite(configured)) {
        return DEFAULT_RATE_LIMIT_DELAY_MS;
    }

    return Math.min(Math.max(configured, 1000), 120000);
}

function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function isRateLimitError(error: unknown): boolean {
    const message = error instanceof Error ? error.message : String(error);
    return /429|rate limit|quota|resource exhausted/i.test(message);
}

async function createGoogleClient(): Promise<GoogleGenAI> {
    const apiKey = await getAICredential('google') ||
        process.env.GEMINI_API_KEY ||
        process.env.GOOGLE_API_KEY ||
        '';

    return new GoogleGenAI({ apiKey });
}

async function generateContentWithBackoff(
    client: GoogleGenAI,
    request: Parameters<GoogleGenAI['models']['generateContent']>[0],
) {
    try {
        await sleep(getProcessDelayMs());
        return await client.models.generateContent(request);
    } catch (error) {
        if (!isRateLimitError(error)) {
            throw error;
        }

        await sleep(getRateLimitDelayMs());
        return client.models.generateContent(request);
    }
}

async function getGoogleWorkflowModel(purpose: 'extraction' | 'graph'): Promise<string> {
    const preference = await getWorkflowModelPreference(purpose);
    if (preference.provider === 'google') {
        return preference.model;
    }

    return purpose === 'extraction'
        ? process.env.GEMINI_MODEL_EXTRACTION || process.env.GEMINI_MODEL_FLASH_LITE || 'gemini-3.1-flash-lite'
        : process.env.GEMINI_MODEL_GRAPH || process.env.GEMINI_MODEL_FLASH || 'gemini-3.1-flash';
}

// Models — Gemini 3 Flash (fast tasks) + Gemini 3.1 Pro (intelligent tasks)

interface ProcessingResult {
    success: boolean;
    fileId: string;
    stage: string;
    progress: number;
    content?: string;
    error?: string;
}

/**
 * POST /api/upload/process - Process uploaded files
 * 
 * Handles file processing including:
 * - Text extraction from documents
 * - Audio/video transcription with Gemini 3 Flash
 * - OCR for images
 * - Spreadsheet parsing
 * - Graph ingestion
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
    try {
        const body = await request.json();
        const { fileId, action } = body;

        if (!fileId) {
            return NextResponse.json(
                { success: false, error: 'fileId is required' },
                { status: 400 }
            );
        }

        // Get file info from database
        const fileResult = await pool.query(
            'SELECT * FROM received_data WHERE id = $1',
            [fileId]
        );

        if (fileResult.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'File not found' },
                { status: 404 }
            );
        }

        const file = fileResult.rows[0];
        const category = file.category;

        // Update status to processing
        await updateFileStatus(fileId, 'processing', 'analyzing', 10);

        let result: ProcessingResult;

        switch (action || category) {
            case 'transcribe':
            case 'audio':
            case 'video':
                result = await processAudioVideo(fileId, file);
                break;

            case 'extract':
            case 'pdf':
            case 'document':
                result = await processDocument(fileId, file);
                break;

            case 'parse':
            case 'spreadsheet':
                result = await processSpreadsheet(fileId, file);
                break;

            case 'ocr':
            case 'image':
                result = await processImage(fileId, file);
                break;

            case 'data':
                result = await processDataFile(fileId, file);
                break;

            default:
                result = await processGenericFile(fileId, file);
        }

        return NextResponse.json(result);
    } catch (error) {
        console.error('Processing error:', error);
        return NextResponse.json(
            { success: false, error: 'Processing failed' },
            { status: 500 }
        );
    }
}

/**
 * Process audio/video files - Transcription with Gemini 3.0 Flash
 */
async function processAudioVideo(fileId: string, file: Record<string, unknown>): Promise<ProcessingResult> {
    try {
        await updateFileStatus(fileId, 'processing', 'transcribe', 20);

        const filePath = file.file_path as string;
        const fileBuffer = await readFile(filePath);
        const base64Data = fileBuffer.toString('base64');

        await updateFileStatus(fileId, 'processing', 'transcribe', 40);

        const prompt = `Transcribe this audio file into a clean, readable format.

Instructions:
1. Identify different speakers if present (Speaker 1, Speaker 2, etc.)
2. Add timestamps at the start of each speaker turn or paragraph [MM:SS]
3. Use clear paragraph breaks for readability
4. Mark unclear sections as [inaudible] or [unclear]
5. Include any important non-speech sounds in brackets [phone ringing], [laughter]

Format the output as clean markdown with:
- A brief summary at the top
- Speaker labels in bold
- Timestamps in brackets
- Clear paragraph structure

Begin transcription:`;

        const mimeType = (file.file_type as string) || 'audio/mpeg';
        const client = await createGoogleClient();
        const extractionModel = await getGoogleWorkflowModel('extraction');

        // Using the new @google/genai SDK API
        const result = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: [
                {
                    role: 'user',
                    parts: [
                        { text: prompt },
                        {
                            inlineData: {
                                mimeType: mimeType,
                                data: base64Data,
                            },
                        },
                    ],
                },
            ],
        });

        await updateFileStatus(fileId, 'processing', 'transcribe', 70);

        const transcript = result.text || '';

        // Generate AI summary
        await updateFileStatus(fileId, 'processing', 'analyze', 80);

        const summaryResult = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: `You are a GDPR Data Protection expert. Analyze and summarize this transcript from a file included in a user's GDPR data access request.

Provide a structured summary in **Markdown** with:
- **Document Type**: What kind of content this is (voice message, meeting recording, etc.)
- **Personal Data Found**: List any personal identifiers (names, emails, phone numbers, addresses, IDs)
- **Key Topics**: 3-5 bullet points summarizing the main content
- **GDPR Relevance**: How this data relates to the individual's privacy rights
- **Risk Assessment**: LOW / MEDIUM / HIGH — based on sensitivity of personal data present

Transcript:\n\n${transcript}`,
        });
        const aiSummary = summaryResult.text || '';

        // Update database with results
        await pool.query(
            `UPDATE received_data 
             SET status = 'completed', 
                 processing_stage = 'completed',
                 processing_progress = 100,
                 transcript = $1,
                 markdown_content = $1,
                 ai_summary = $2,
                 processing_completed_at = NOW()
             WHERE id = $3`,
            [transcript, aiSummary, fileId]
        );
        await replaceArtifactsForFile({ ...file, id: fileId, ai_summary: aiSummary } as any, transcript);

        return {
            success: true,
            fileId,
            stage: 'completed',
            progress: 100,
            content: transcript,
        };
    } catch (error) {
        console.error('Audio/video processing error:', error);
        await updateFileStatus(fileId, 'error', 'transcribe', 0, String(error));
        return {
            success: false,
            fileId,
            stage: 'error',
            progress: 0,
            error: String(error),
        };
    }
}

/**
 * Process PDF/Document files - Text extraction with Gemini
 */
async function processDocument(fileId: string, file: Record<string, unknown>): Promise<ProcessingResult> {
    try {
        await updateFileStatus(fileId, 'processing', 'extract', 20);

        const filePath = file.file_path as string;
        const fileBuffer = await readFile(filePath);
        const base64Data = fileBuffer.toString('base64');

        await updateFileStatus(fileId, 'processing', 'extract', 40);

        const mimeType = (file.file_type as string) || 'application/pdf';
        const client = await createGoogleClient();
        const extractionModel = await getGoogleWorkflowModel('extraction');

        const result = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: [
                {
                    role: 'user',
                    parts: [
                        {
                            text: `You are a GDPR Data Protection expert. Extract all text from this document and format as clean **Markdown**.

IMPORTANT INSTRUCTIONS:
- Preserve document structure: headers (use # notation), lists, tables, and emphasis
- If this is an **HTML file**, extract the semantic content cleanly (strip tags, preserve meaning)
- Include a brief **Summary** section at the very top with: document type, key personal data found, and GDPR relevance
- Mark any personal identifiers you find with **bold** formatting
- If the document contains privacy policies or terms of service, extract the key data processing sections verbatim` },
                        {
                            inlineData: {
                                mimeType: mimeType,
                                data: base64Data,
                            },
                        },
                    ],
                },
            ],
        });

        await updateFileStatus(fileId, 'processing', 'analyze', 70);

        const extractedText = result.text || '';

        // Generate summary
        const summaryResult = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: `You are a GDPR Data Protection expert. Summarize this document from a user's GDPR data access request.

Provide a structured summary in **Markdown** with:
- **Document Type**: What kind of document this is (privacy policy, account data export, communication log, etc.)
- **Personal Data Found**: List specific personal identifiers discovered (names, emails, IDs, etc.)
- **Data Processing Activities**: Any mentions of how data is collected, stored, shared, or deleted
- **Legal Basis**: Any legal justifications mentioned (consent, legitimate interest, contract, etc.)
- **Third Parties**: Companies, partners, or services mentioned that may receive personal data
- **Risk Assessment**: LOW / MEDIUM / HIGH — based on data sensitivity and exposure

Document Content:\n\n${extractedText.substring(0, 10000)}`,
        });
        const aiSummary = summaryResult.text || '';

        // Optional: Structured GDPR extraction via Python LangExtract service
        let extractedEntities = null;
        try {
            const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001';
            const extractResponse = await fetch(`${intelligenceUrl}/extract/file`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: extractedText.substring(0, 50000),
                    file_name: file.file_name as string,
                    file_id: fileId,
                    request_id: file.request_id as string,
                    company_name: (file.company_name as string) || '',
                    extraction_passes: 2,
                }),
                signal: AbortSignal.timeout(120000), // 2 min timeout
            });
            if (extractResponse.ok) {
                const extractResult = await extractResponse.json();
                if (extractResult.success && extractResult.entity_count > 0) {
                    extractedEntities = extractResult.entities;
                    console.log(`[LangExtract] Extracted ${extractResult.entity_count} entities from ${file.file_name}`);
                }
            }
        } catch (langextractError) {
            // LangExtract is optional — don't fail the whole process
            console.warn('[LangExtract] Service unavailable, skipping structured extraction:', langextractError);
        }

        await updateFileStatus(fileId, 'processing', 'saving', 90);

        await pool.query(
            `UPDATE received_data 
             SET status = 'completed', 
                 processing_stage = 'completed',
                 processing_progress = 100,
                 extracted_text = $1,
                 markdown_content = $1,
                 ai_summary = $2,
                 ${extractedEntities ? 'extracted_entities = $4::jsonb,' : ''}
                 processing_completed_at = NOW()
             WHERE id = $3`,
            extractedEntities
                ? [extractedText, aiSummary, fileId, JSON.stringify(extractedEntities)]
                : [extractedText, aiSummary, fileId]
        );
        await replaceArtifactsForFile({ ...file, id: fileId, ai_summary: aiSummary } as any, extractedText);

        return {
            success: true,
            fileId,
            stage: 'completed',
            progress: 100,
            content: extractedText,
        };
    } catch (error) {
        console.error('Document processing error:', error);
        await updateFileStatus(fileId, 'error', 'extract', 0, String(error));
        return {
            success: false,
            fileId,
            stage: 'error',
            progress: 0,
            error: String(error),
        };
    }
}

/**
 * Process spreadsheet files - Parse and convert to markdown
 */
async function processSpreadsheet(fileId: string, file: Record<string, unknown>): Promise<ProcessingResult> {
    try {
        await updateFileStatus(fileId, 'processing', 'parse', 20);

        const filePath = file.file_path as string;
        const fileBuffer = await readFile(filePath);
        const base64Data = fileBuffer.toString('base64');

        await updateFileStatus(fileId, 'processing', 'parse', 40);

        const mimeType = (file.file_type as string) || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
        const client = await createGoogleClient();
        const extractionModel = await getGoogleWorkflowModel('extraction');

        const result = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: [
                {
                    role: 'user',
                    parts: [
                        { text: 'Parse this spreadsheet and convert to markdown tables. Preserve all data, column headers, and sheet names. Add a summary of the data at the top.' },
                        {
                            inlineData: {
                                mimeType: mimeType,
                                data: base64Data,
                            },
                        },
                    ],
                },
            ],
        });

        await updateFileStatus(fileId, 'processing', 'analyze', 70);

        const extractedContent = result.text || '';

        const summaryResult = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: `You are a GDPR Data Protection expert. Summarize this spreadsheet data from a user's GDPR data access request.

Provide a structured summary in **Markdown** with:
- **Data Type**: What this spreadsheet contains (transaction history, contact list, activity log, etc.)
- **Personal Data Columns**: Which columns contain personal identifiers
- **Record Count**: Approximate number of data records
- **Date Range**: Earliest and latest dates if applicable
- **Sensitive Categories**: Any special category data (health, financial, political, biometric)
- **Risk Assessment**: LOW / MEDIUM / HIGH

Spreadsheet Content:\n\n${extractedContent.substring(0, 10000)}`,
        });
        const aiSummary = summaryResult.text || '';

        await pool.query(
            `UPDATE received_data 
             SET status = 'completed', 
                 processing_stage = 'completed',
                 processing_progress = 100,
                 extracted_text = $1,
                 markdown_content = $1,
                 ai_summary = $2,
                 processing_completed_at = NOW()
             WHERE id = $3`,
            [extractedContent, aiSummary, fileId]
        );
        await replaceArtifactsForFile({ ...file, id: fileId, ai_summary: aiSummary } as any, extractedContent);

        return {
            success: true,
            fileId,
            stage: 'completed',
            progress: 100,
            content: extractedContent,
        };
    } catch (error) {
        console.error('Spreadsheet processing error:', error);
        await updateFileStatus(fileId, 'error', 'parse', 0, String(error));
        return {
            success: false,
            fileId,
            stage: 'error',
            progress: 0,
            error: String(error),
        };
    }
}

/**
 * Process image files - OCR with Gemini Vision
 */
async function processImage(fileId: string, file: Record<string, unknown>): Promise<ProcessingResult> {
    try {
        await updateFileStatus(fileId, 'processing', 'ocr', 20);

        const filePath = file.file_path as string;
        const fileBuffer = await readFile(filePath);
        const base64Data = fileBuffer.toString('base64');

        await updateFileStatus(fileId, 'processing', 'ocr', 50);

        const mimeType = (file.file_type as string) || 'image/jpeg';
        const client = await createGoogleClient();
        const extractionModel = await getGoogleWorkflowModel('extraction');

        const result = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: [
                {
                    role: 'user',
                    parts: [
                        { text: 'Extract all text visible in this image. If it contains a form, table, or structured data, format as markdown. Describe any non-text elements briefly.' },
                        {
                            inlineData: {
                                mimeType: mimeType,
                                data: base64Data,
                            },
                        },
                    ],
                },
            ],
        });

        const extractedText = result.text || '';

        await pool.query(
            `UPDATE received_data 
             SET status = 'completed', 
                 processing_stage = 'completed',
                 processing_progress = 100,
                 extracted_text = $1,
                 markdown_content = $1,
                 processing_completed_at = NOW()
             WHERE id = $2`,
            [extractedText, fileId]
        );
        await replaceArtifactsForFile({ ...file, id: fileId } as any, extractedText);

        return {
            success: true,
            fileId,
            stage: 'completed',
            progress: 100,
            content: extractedText,
        };
    } catch (error) {
        console.error('Image processing error:', error);
        await updateFileStatus(fileId, 'error', 'ocr', 0, String(error));
        return {
            success: false,
            fileId,
            stage: 'error',
            progress: 0,
            error: String(error),
        };
    }
}

/**
 * Process data files (JSON, XML, etc.)
 */
async function processDataFile(fileId: string, file: Record<string, unknown>): Promise<ProcessingResult> {
    try {
        await updateFileStatus(fileId, 'processing', 'parse', 20);

        const filePath = file.file_path as string;
        const fileContent = await readFile(filePath, 'utf-8');

        await updateFileStatus(fileId, 'processing', 'analyze', 50);
        const client = await createGoogleClient();
        const extractionModel = await getGoogleWorkflowModel('extraction');

        const result = await generateContentWithBackoff(client, {
            model: extractionModel,
            contents: `Analyze this data file and convert to a readable markdown format. Summarize the key data structures and important values:\n\n${fileContent.substring(0, 50000)}`,
        });

        const markdownContent = result.text || '';

        await pool.query(
            `UPDATE received_data 
             SET status = 'completed', 
                 processing_stage = 'completed',
                 processing_progress = 100,
                 extracted_text = $1,
                 markdown_content = $2,
                 processing_completed_at = NOW()
             WHERE id = $3`,
            [fileContent.substring(0, 100000), markdownContent, fileId]
        );
        await replaceArtifactsForFile({ ...file, id: fileId, ai_summary: markdownContent } as any, fileContent);

        return {
            success: true,
            fileId,
            stage: 'completed',
            progress: 100,
            content: markdownContent,
        };
    } catch (error) {
        console.error('Data file processing error:', error);
        await updateFileStatus(fileId, 'error', 'parse', 0, String(error));
        return {
            success: false,
            fileId,
            stage: 'error',
            progress: 0,
            error: String(error),
        };
    }
}

/**
 * Process generic/other files
 */
async function processGenericFile(fileId: string, file: Record<string, unknown>): Promise<ProcessingResult> {
    try {
        await updateFileStatus(fileId, 'processing', 'analyze', 30);

        // Just mark as completed with basic info
        await pool.query(
            `UPDATE received_data 
             SET status = 'completed', 
                 processing_stage = 'completed',
                 processing_progress = 100,
                 ai_summary = 'File type not supported for content extraction.',
                 processing_completed_at = NOW()
             WHERE id = $1`,
            [fileId]
        );

        return {
            success: true,
            fileId,
            stage: 'completed',
            progress: 100,
            content: 'File stored successfully. Content extraction not available for this file type.',
        };
    } catch (error) {
        console.error('Generic file processing error:', error);
        await updateFileStatus(fileId, 'error', 'analyze', 0, String(error));
        return {
            success: false,
            fileId,
            stage: 'error',
            progress: 0,
            error: String(error),
        };
    }
}

/**
 * Helper to update file status in database
 */
async function updateFileStatus(
    fileId: string,
    status: string,
    stage: string,
    progress: number,
    errorMessage?: string
): Promise<void> {
    if (errorMessage) {
        await pool.query(
            `UPDATE received_data 
             SET status = $1, processing_stage = $2, processing_progress = $3, error_message = $4
             WHERE id = $5`,
            [status, stage, progress, errorMessage, fileId]
        );
    } else {
        await pool.query(
            `UPDATE received_data 
             SET status = $1, processing_stage = $2, processing_progress = $3
             WHERE id = $4`,
            [status, stage, progress, fileId]
        );
    }
}

/**
 * Send processed content to KG Ingestor N8N workflow for graph ingestion
 */
async function ingestToGraph(
    fileId: string,
    content: string,
    requestId: string | null,
    companyName: string
): Promise<{ success: boolean; error?: string }> {
    try {
        const N8N_WEBHOOK_INGEST = process.env.N8N_WEBHOOK_INGEST_DATA || 'http://localhost:5678/webhook-test/ingest-data';
        const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001';

        // First, extract entities using the graph workflow model. Defaults to Flash, not Pro.
        const extractionPrompt = `You are a GDPR Data Protection and Knowledge Graph expert. Your task is to analyze this document — which is part of a user's GDPR data access request to the company "${companyName || 'Unknown'}" — and extract structured data for a privacy knowledge graph.

The knowledge graph tracks:
- What personal data exists about the individual
- Which companies/services hold or process that data
- The relationships between data points, companies, and legal bases
- Risk levels for different types of data exposure

Extract ALL of the following categories (be thorough — even partial mentions count):

1. **Personal Data Types** — names, emails, phone numbers, addresses, IP addresses, device IDs, financial info, health data, biometric data, location data, employment data, social media handles
2. **Data Holders / Companies** — any organization that collects, stores, or processes the data
3. **Dates & Time Periods** — when data was collected, processed, or retained
4. **Processing Activities** — what is being done with the data (storage, sharing, analysis, profiling, marketing, automated decision-making)
5. **Legal Basis** — consent, contract, legitimate interest, vital interest, public task, legal obligation
6. **Third Parties** — data sharing partners, sub-processors, advertising networks, analytics providers
7. **Consent Mechanisms** — opt-in, opt-out, cookie consent, marketing preferences
8. **Data Retention** — how long data is kept, deletion policies, archival periods
9. **Cross-border Transfers** — data sent to other countries, adequacy decisions, standard contractual clauses
10. **Breach Indicators** — any mentions of data leaks, unauthorized access, security incidents

EDGE CASE HANDLING:
- If the document is empty or contains only binary/encoded content, return empty arrays.
- If an entity appears multiple times, include it only once but note the frequency.
- Avoid overly generic entries (e.g., "data" alone is too vague — be specific).
- For ambiguous entries, include them but with confidence: "LOW".

Output as JSON with this structure:
{
  "extractedData": [
    { "type": "PERSON", "value": "John Smith", "category": "IDENTITY", "riskLevel": "HIGH", "confidence": "HIGH" },
    { "type": "EMAIL", "value": "john@example.com", "category": "CONTACT", "riskLevel": "MEDIUM", "confidence": "HIGH" },
    { "type": "COMPANY", "value": "AnalyticsCo", "category": "THIRD_PARTY", "riskLevel": "MEDIUM", "confidence": "MEDIUM" },
    { "type": "LEGAL_BASIS", "value": "Legitimate Interest", "category": "LEGAL", "riskLevel": "LOW", "confidence": "HIGH" }
  ],
  "categories": {
    "IDENTITY": { "count": 1, "examples": ["John Smith"], "riskLevel": "HIGH" },
    "CONTACT": { "count": 1, "examples": ["john@example.com"], "riskLevel": "MEDIUM" },
    "THIRD_PARTY": { "count": 1, "examples": ["AnalyticsCo"], "riskLevel": "MEDIUM" },
    "LEGAL": { "count": 1, "examples": ["Legitimate Interest"], "riskLevel": "LOW" }
  },
  "relationships": [
    { "subject": "John Smith", "predicate": "HAS_EMAIL", "object": "john@example.com" },
    { "subject": "${companyName || 'Unknown'}", "predicate": "SHARES_DATA_WITH", "object": "AnalyticsCo" }
  ]
}

Document Content:
${content.substring(0, 20000)}`;

        const client = await createGoogleClient();
        const graphModel = await getGoogleWorkflowModel('graph');
        const extractResult = await generateContentWithBackoff(client, {
            model: graphModel,
            contents: extractionPrompt,
        });

        let extractedJson = {};
        const responseText = extractResult.text || '{}';

        // Parse JSON from response (handle markdown code blocks)
        const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, responseText];
        try {
            extractedJson = JSON.parse(jsonMatch[1] || responseText);
        } catch {
            extractedJson = { extractedData: [], categories: {} };
        }

        const ingestPayload = {
            requestId: requestId || fileId,
            request_id: requestId || fileId,
            companyName: companyName || 'Unknown',
            company_name: companyName || 'Unknown',
            extractedData: (extractedJson as { extractedData?: unknown[] }).extractedData || [],
            extracted_data: (extractedJson as { extractedData?: unknown[] }).extractedData || [],
            categories: (extractedJson as { categories?: Record<string, unknown> }).categories || {},
            source: 'file_upload',
            fileId: fileId,
        };

        let ingestionSucceeded = false;
        let ingestionError = '';

        // Prefer the built-in Python KG ingestor. N8N remains an optional fallback.
        try {
            const response = await fetch(`${intelligenceUrl}/ingest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_name: ingestPayload.company_name,
                    request_id: ingestPayload.request_id,
                    extracted_data: ingestPayload.extracted_data,
                    categories: ingestPayload.categories,
                    source: ingestPayload.source,
                }),
                signal: AbortSignal.timeout(120000),
            });

            if (response.ok) {
                const result = await response.json();
                ingestionSucceeded = result.success !== false;
                ingestionError = result.errors?.join('; ') || '';
            } else {
                ingestionError = `Intelligence ingestor returned ${response.status}`;
            }
        } catch (error) {
            ingestionError = `Intelligence ingestor unavailable: ${String(error)}`;
        }

        if (!ingestionSucceeded) {
            console.warn('[Graph ingestion] Falling back to N8N:', ingestionError);
        }

        const response = ingestionSucceeded ? null : await fetch(N8N_WEBHOOK_INGEST, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(ingestPayload),
        });

        if (response && !response.ok) {
            throw new Error(`${ingestionError}; N8N webhook returned ${response.status}`);
        }

        // Update database to mark as ingested
        await pool.query(
            `UPDATE received_data 
             SET graph_ingested = true, 
                 entities_extracted = $1
             WHERE id = $2`,
            [JSON.stringify(extractedJson), fileId]
        );

        return { success: true };
    } catch (error) {
        console.error('Graph ingestion error:', error);
        return { success: false, error: String(error) };
    }
}

/**
 * POST /api/upload/ingest - Trigger graph ingestion for a processed file
 */
export async function PUT(request: NextRequest): Promise<NextResponse> {
    try {
        const body = await request.json();
        const { fileId } = body;

        if (!fileId) {
            return NextResponse.json(
                { success: false, error: 'fileId is required' },
                { status: 400 }
            );
        }

        // Get file and its content from database
        const fileResult = await pool.query(
            'SELECT * FROM received_data WHERE id = $1',
            [fileId]
        );

        if (fileResult.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'File not found' },
                { status: 404 }
            );
        }

        const file = fileResult.rows[0];
        const content = file.markdown_content || file.extracted_text || file.transcript || '';

        if (!content) {
            return NextResponse.json(
                { success: false, error: 'No processed content available for ingestion' },
                { status: 400 }
            );
        }

        await updateFileStatus(fileId, 'processing', 'ingest', 85);

        // Get request info if available
        let companyName = 'Unknown Company';
        if (file.request_id) {
            const reqResult = await pool.query(
                'SELECT company_name FROM requests WHERE id = $1',
                [file.request_id]
            );
            if (reqResult.rows.length > 0) {
                companyName = reqResult.rows[0].company_name;
            }
        }

        const result = await ingestToGraph(fileId, content, file.request_id, companyName);

        if (result.success) {
            await updateFileStatus(fileId, 'completed', 'completed', 100);
            return NextResponse.json({
                success: true,
                fileId,
                message: 'Content ingested to knowledge graph'
            });
        } else {
            await updateFileStatus(fileId, 'error', 'ingest', 85, result.error);
            return NextResponse.json(
                { success: false, error: result.error },
                { status: 500 }
            );
        }
    } catch (error) {
        console.error('Ingestion error:', error);
        return NextResponse.json(
            { success: false, error: 'Ingestion failed' },
            { status: 500 }
        );
    }
}

