import { NextResponse } from 'next/server';
import { pool } from '@/lib/db';
import { readFile } from 'fs/promises';
import { GoogleGenAI } from '@google/genai';
import { getAICredential } from '@/lib/ai-credentials';
import { getWorkflowModelPreference } from '@/lib/model-preferences';
import { replaceArtifactsForFile } from '@/lib/data-artifacts';

const DEFAULT_SCAN_DELAY_MS = 1500;
const DEFAULT_RATE_LIMIT_DELAY_MS = 10000;

function getScanDelayMs(): number {
    const configured = Number(process.env.UPLOAD_SCAN_DELAY_MS);
    if (!Number.isFinite(configured)) {
        return DEFAULT_SCAN_DELAY_MS;
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
        return await client.models.generateContent(request);
    } catch (error) {
        if (!isRateLimitError(error)) {
            throw error;
        }

        await sleep(getRateLimitDelayMs());
        return client.models.generateContent(request);
    }
}

/**
 * POST /api/upload/scan - Scan for unprocessed files and process them
 * 
 * Finds files that haven't been processed yet (no extracted text, no summary,
 * or no graph ingestion) and processes them automatically.
 */
export async function POST() {
    const results = {
        scanned: 0,
        processed: 0,
        ingested: 0,
        errors: [] as string[],
    };

    try {
        // 1. Find files that need text extraction (status is pending/error, or no extracted content)
        const unprocessedResult = await pool.query(`
            SELECT rd.*, r.company_name 
            FROM received_data rd
            LEFT JOIN requests r ON rd.request_id = r.id
            WHERE (rd.status = 'pending' OR rd.status = 'error' OR rd.status = 'uploaded')
               OR (rd.extracted_text IS NULL AND rd.transcript IS NULL AND rd.markdown_content IS NULL AND rd.status != 'processing')
            ORDER BY rd.date_received ASC
        `);

        results.scanned = unprocessedResult.rows.length;

        // 2. Process each unprocessed file
        for (const file of unprocessedResult.rows) {
            try {
                await sleep(getScanDelayMs());
                const content = await extractContent(file);
                if (content) {
                    await sleep(getScanDelayMs());
                    // Generate AI summary
                    const summary = await generateSummary(content, file.file_name);

                    // Update database with extracted content and summary
                    await pool.query(`
                        UPDATE received_data 
                        SET extracted_text = $1,
                            ai_summary = $2,
                            status = 'completed',
                            processing_stage = 'completed',
                            processing_progress = 80
                        WHERE id = $3
                    `, [content.substring(0, 50000), summary, file.id]);
                    await replaceArtifactsForFile({ ...file, ai_summary: summary }, content);

                    results.processed++;
                }
            } catch (err) {
                const errorMsg = `Failed to process ${file.file_name}: ${err}`;
                console.error(errorMsg);
                results.errors.push(errorMsg);
                await pool.query(
                    `UPDATE received_data SET status = 'error', error_message = $1 WHERE id = $2`,
                    [String(err).substring(0, 500), file.id]
                );
            }
        }

        // 3. Find files that have content but haven't been ingested to graph
        const unIngestedResult = await pool.query(`
            SELECT rd.*, r.company_name 
            FROM received_data rd
            LEFT JOIN requests r ON rd.request_id = r.id
            WHERE rd.status = 'completed'
              AND (rd.extracted_text IS NOT NULL OR rd.transcript IS NOT NULL OR rd.markdown_content IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM analysis_runs ar
                  WHERE ar.run_type = 'legacy_kg_ingestion_adapter'
                    AND ar.status = 'completed'
                    AND ar.configuration->>'legacy_file_id' = rd.id::text
              )
        `);

        // 4. Ingest each to the knowledge graph
        for (const file of unIngestedResult.rows) {
            try {
                await sleep(getScanDelayMs());
                const content = file.markdown_content || file.extracted_text || file.transcript || '';
                if (!content) continue;

                const companyName = file.company_name || 'Unknown Company';
                const ingestionResult = await ingestToGraphDirect(file.id, content, file.request_id, companyName);

                if (ingestionResult.success) {
                    await pool.query(`
                        UPDATE received_data 
                        SET graph_ingested = false,
                            entities_extracted = $1,
                            status = 'completed',
                            processing_stage = 'completed',
                            processing_progress = 100
                        WHERE id = $2
                    `, [JSON.stringify(ingestionResult.entities), file.id]);
                    results.ingested++;
                }
            } catch (err) {
                const errorMsg = `Failed to ingest ${file.file_name}: ${err}`;
                console.error(errorMsg);
                results.errors.push(errorMsg);
            }
        }

        return NextResponse.json({
            success: true,
            message: `Scanned ${results.scanned} files: processed ${results.processed}, submitted ${results.ingested} evidence batches for review`,
            ...results,
        });
    } catch (error) {
        console.error('Scan error:', error);
        return NextResponse.json(
            { success: false, error: 'Scan failed: ' + String(error) },
            { status: 500 }
        );
    }
}

/**
 * Extract text content from a file based on its type
 */
async function extractContent(file: Record<string, any>): Promise<string | null> {
    // If already has content, return it
    if (file.extracted_text || file.transcript || file.markdown_content) {
        return file.markdown_content || file.extracted_text || file.transcript;
    }

    const filePath = file.file_path as string;
    if (!filePath) return null;

    try {
        const fileBuffer = await readFile(filePath);
        const category = file.category || 'other';

        if (['pdf', 'document', 'data'].includes(category)) {
            // Use Gemini to extract text from documents
            const base64Data = fileBuffer.toString('base64');
            const mimeType = getMimeType(file.file_name || '');
            const client = await createGoogleClient();
            const extractionModel = await getWorkflowModelPreference('extraction');

            const response = await generateContentWithBackoff(client, {
                model: extractionModel.provider === 'google' ? extractionModel.model : 'gemini-3.1-flash-lite',
                contents: [{
                    role: 'user',
                    parts: [
                        { text: `Extract all text content from this document. Preserve the structure, headings, lists, and tables. Output as clean markdown.` },
                        { inlineData: { data: base64Data, mimeType } },
                    ],
                }],
            });
            return response.text || null;

        } else if (['image'].includes(category)) {
            // OCR with Gemini Vision
            const base64Data = fileBuffer.toString('base64');
            const mimeType = getMimeType(file.file_name || '');
            const client = await createGoogleClient();
            const extractionModel = await getWorkflowModelPreference('extraction');

            const response = await generateContentWithBackoff(client, {
                model: extractionModel.provider === 'google' ? extractionModel.model : 'gemini-3.1-flash-lite',
                contents: [{
                    role: 'user',
                    parts: [
                        { text: `Extract all text visible in this image using OCR. Also describe any important visual elements, logos, charts, or diagrams.` },
                        { inlineData: { data: base64Data, mimeType } },
                    ],
                }],
            });
            return response.text || null;

        } else if (['audio', 'video'].includes(category)) {
            // Transcribe audio/video
            const base64Data = fileBuffer.toString('base64');
            const mimeType = getMimeType(file.file_name || '');
            const client = await createGoogleClient();
            const extractionModel = await getWorkflowModelPreference('extraction');

            const response = await generateContentWithBackoff(client, {
                model: extractionModel.provider === 'google' ? extractionModel.model : 'gemini-3.1-flash-lite',
                contents: [{
                    role: 'user',
                    parts: [
                        { text: `Transcribe this audio/video file. Identify different speakers if present. Add timestamps. Output as clean markdown.` },
                        { inlineData: { data: base64Data, mimeType } },
                    ],
                }],
            });
            return response.text || null;

        } else if (['spreadsheet'].includes(category)) {
            // For spreadsheets, try to read as text
            const textContent = fileBuffer.toString('utf-8');
            return textContent.substring(0, 50000);
        } else {
            // Generic: try as text
            const textContent = fileBuffer.toString('utf-8');
            if (textContent && textContent.length > 10 && !textContent.includes('\0')) {
                return textContent.substring(0, 50000);
            }
        }
    } catch (err) {
        console.error(`File read error for ${file.file_name}:`, err);
    }

    return null;
}

/**
 * Generate an AI summary of the extracted content
 */
async function generateSummary(content: string, fileName: string): Promise<string> {
    try {
        const client = await createGoogleClient();
        const extractionModel = await getWorkflowModelPreference('extraction');
        const response = await generateContentWithBackoff(client, {
            model: extractionModel.provider === 'google' ? extractionModel.model : 'gemini-3.1-flash-lite',
            contents: `Summarize this document in 2-3 concise sentences. Focus on what personal data or GDPR-relevant information it contains.\n\nFile: ${fileName}\n\nContent:\n${content.substring(0, 10000)}`,
            config: { maxOutputTokens: 200 },
        });
        return response.text || 'No summary available';
    } catch {
        return 'Summary generation failed';
    }
}

/**
 * Submit extraction to the canonical intelligence evidence pipeline.
 */
async function ingestToGraphDirect(
    fileId: string,
    content: string,
    requestId: string | null,
    companyName: string
): Promise<{ success: boolean; entities: any }> {
    const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001';
    const response = await fetch(`${intelligenceUrl}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            company_name: companyName,
            request_id: requestId,
            source: 'file_upload',
            extracted_data: [],
            categories: {},
            source_artifact: { legacy_file_id: fileId, exact_text: content.substring(0, 50000) },
        }),
        signal: AbortSignal.timeout(60000),
    });
    if (!response.ok) throw new Error(`Canonical evidence ingestion returned ${response.status}`);
    const result = await response.json();
    return { success: result.success === true, entities: result };
}

function getMimeType(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    const mimeTypes: Record<string, string> = {
        pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg',
        png: 'image/png', gif: 'image/gif', csv: 'text/csv',
        xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        xls: 'application/vnd.ms-excel', txt: 'text/plain', json: 'application/json',
        xml: 'application/xml', mp3: 'audio/mpeg', wav: 'audio/wav', m4a: 'audio/mp4',
        mp4: 'video/mp4', doc: 'application/msword',
        docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    };
    return mimeTypes[ext] || 'application/octet-stream';
}
