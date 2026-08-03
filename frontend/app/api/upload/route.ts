import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { writeFile, mkdir, unlink, rm } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
import type { PoolClient } from 'pg';
import { pool } from '@/lib/db';
import AdmZip from 'adm-zip';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

// Upload directory (local storage)
const UPLOAD_DIR = path.join(process.cwd(), 'uploads');

/**
 * POST /api/upload - Upload files and store metadata
 * 
 * Accepts multipart form data with files and stores them locally.
 * Creates records in received_data table for tracking.
 */
export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    let uploadClient: PoolClient | null = null;
    let batchDir: string | null = null;
    try {
        const formData = await request.formData();
        const files = formData.getAll('files') as File[];
        const requestId = formData.get('requestId') as string | null;
        const sourceZip = formData.get('sourceZip') as string | null;

        if (requestId) {
            if (!await requests.get(authority.profileId, requestId)) {
                return NextResponse.json({ success: false, error: 'Request not found' }, { status: 404 });
            }
        }

        if (!files || files.length === 0) {
            return NextResponse.json(
                { success: false, error: 'No files provided' },
                { status: 400 }
            );
        }

        // Ensure upload directory exists
        if (!existsSync(UPLOAD_DIR)) {
            await mkdir(UPLOAD_DIR, { recursive: true });
        }

        // Create subdirectory for this upload batch
        const batchId = `batch_${randomUUID()}`;
        batchDir = path.join(UPLOAD_DIR, batchId);
        await mkdir(batchDir, { recursive: true });
        const client = await pool.connect();
        uploadClient = client;
        await client.query('BEGIN');

        const uploadedFiles: Array<{
            id: string;
            fileName: string;
            filePath: string;
            fileSize: number;
            fileType: string;
            category: string;
            status: string;
        }> = [];

        for (const file of files) {
            const bytes = await file.arrayBuffer();
            const buffer = Buffer.from(bytes);

            // Check if this is a ZIP file — extract its contents server-side
            const ext = file.name.split('.').pop()?.toLowerCase();
            if (ext === 'zip') {
                let zipOpened = false;
                try {
                    const zip = new AdmZip(buffer);
                    const entries = zip.getEntries();
                    zipOpened = true;
                    const zipSubDir = path.join(batchDir, randomUUID());
                    await mkdir(zipSubDir, { recursive: true });

                    for (const entry of entries) {
                        // Skip directories and hidden files
                        if (entry.isDirectory || entry.entryName.startsWith('__MACOSX') || entry.entryName.startsWith('.')) continue;

                        const entryName = path.basename(entry.entryName);
                        if (!entryName) continue;

                        const sanitizedEntry = `${randomUUID()}_${entryName.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
                        const entryPath = path.join(zipSubDir, sanitizedEntry);
                        const entryData = entry.getData();

                        await writeFile(entryPath, entryData);

                        const entryCategory = categorizeFile(entryName);
                        const entrySizeMb = entryData.length / (1024 * 1024);
                        const entryMime = getMimeType(entryName);

                        const result = await client.query(
                            `INSERT INTO received_data 
                             (request_id, file_name, original_name, file_path, file_size_mb, file_type, category, status, processing_stage, profile_id)
                             VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', 'upload', $8)
                             RETURNING id`,
                            [requestId, sanitizedEntry, `${file.name}/${entryName}`, entryPath, entrySizeMb, entryMime, entryCategory, authority.profileId]
                        );

                        uploadedFiles.push({
                            id: result.rows[0].id,
                            fileName: sanitizedEntry,
                            filePath: entryPath,
                            fileSize: entryData.length,
                            fileType: entryMime,
                            category: entryCategory,
                            status: 'pending',
                        });
                    }
                } catch (zipErr) {
                    if (zipOpened) throw zipErr;
                    console.error('Failed to extract ZIP:', zipErr);
                    // Fall through — store the ZIP as-is below
                    const sanitizedName = `${randomUUID()}_${file.name.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
                    const filePath = path.join(batchDir, sanitizedName);
                    await writeFile(filePath, buffer);
                    const category = categorizeFile(file.name);
                    const fileSizeMb = file.size / (1024 * 1024);
                    const result = await client.query(
                        `INSERT INTO received_data 
                         (request_id, file_name, original_name, file_path, file_size_mb, file_type, category, status, processing_stage, profile_id)
                         VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', 'upload', $8)
                         RETURNING id`,
                        [requestId, sanitizedName, file.name, filePath, fileSizeMb, file.type || 'application/zip', category, authority.profileId]
                    );
                    uploadedFiles.push({
                        id: result.rows[0].id,
                        fileName: sanitizedName,
                        filePath: filePath,
                        fileSize: file.size,
                        fileType: file.type || 'application/zip',
                        category: category,
                        status: 'pending',
                    });
                }
                continue; // Skip normal file handling below
            }

            // Normal (non-ZIP) file handling
            const sanitizedName = `${randomUUID()}_${file.name.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
            const filePath = path.join(batchDir, sanitizedName);

            // Write file to disk
            await writeFile(filePath, buffer);

            // Determine file category
            const category = categorizeFile(file.name);
            const fileSizeMb = file.size / (1024 * 1024);

            // Insert into database
            const result = await client.query(
                `INSERT INTO received_data 
                 (request_id, file_name, original_name, file_path, file_size_mb, file_type, category, status, processing_stage, profile_id)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', 'upload', $8)
                 RETURNING id`,
                [
                    requestId,
                    sanitizedName,
                    file.name,
                    filePath,
                    fileSizeMb,
                    file.type || getMimeType(file.name),
                    category,
                    authority.profileId,
                ]
            );

            uploadedFiles.push({
                id: result.rows[0].id,
                fileName: sanitizedName,
                filePath: filePath,
                fileSize: file.size,
                fileType: file.type || getMimeType(file.name),
                category: category,
                status: 'pending',
            });
        }

        await client.query('COMMIT');
        return NextResponse.json({
            success: true,
            batchId,
            files: uploadedFiles,
            totalFiles: uploadedFiles.length,
            totalSizeMb: uploadedFiles.reduce((sum, f) => sum + f.fileSize / (1024 * 1024), 0).toFixed(2),
        });
    } catch (error) {
        if (uploadClient) await uploadClient.query('ROLLBACK').catch(() => undefined);
        if (batchDir && batchDir.startsWith(`${UPLOAD_DIR}${path.sep}`)) {
            await rm(batchDir, { recursive: true, force: true }).catch(() => undefined);
        }
        console.error('Upload error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to upload files' },
            { status: 500 }
        );
    } finally {
        uploadClient?.release();
    }
}

/**
 * GET /api/upload - Get file status by ID or batch
 */
export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const searchParams = request.nextUrl.searchParams;
    const fileId = searchParams.get('fileId');
    const requestId = searchParams.get('requestId');

    try {
        let query = 'SELECT * FROM received_data WHERE profile_id = $1';
        let params: string[] = [authority.profileId];

        if (fileId) {
            query += ' AND id = $2';
            params.push(fileId);
        } else if (requestId) {
            query += ' AND request_id = $2 ORDER BY date_received DESC';
            params.push(requestId);
        } else {
            query += ' ORDER BY date_received DESC LIMIT 50';
        }

        const result = await pool.query(query, params);

        return NextResponse.json({
            success: true,
            files: result.rows.map((row) => ({
                id: row.id,
                requestId: row.request_id,
                fileName: row.file_name,
                originalName: row.original_name,
                filePath: row.file_path,
                fileSizeMb: parseFloat(row.file_size_mb) || 0,
                fileType: row.file_type,
                category: row.category,
                status: row.status,
                processingStage: row.processing_stage,
                processingProgress: row.processing_progress || 0,
                extractedText: row.extracted_text,
                markdownContent: row.markdown_content,
                transcript: row.transcript,
                aiSummary: row.ai_summary,
                entitiesExtracted: row.entities_extracted,
                graphIngested: row.graph_ingested,
                errorMessage: row.error_message,
                dateReceived: row.date_received,
            })),
        });
    } catch (error) {
        console.error('Failed to get files:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to retrieve files' },
            { status: 500 }
        );
    }
}

/**
 * PATCH /api/upload - Update file processing status
 */
export async function PATCH(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json();
        const { fileId, status, processingStage, processingProgress, extractedText, markdownContent, transcript, aiSummary, entitiesExtracted, graphIngested, errorMessage } = body;

        if (!fileId) {
            return NextResponse.json(
                { success: false, error: 'fileId is required' },
                { status: 400 }
            );
        }

        const updates: string[] = [];
        const values: (string | number | boolean | object | null)[] = [];
        let paramIndex = 1;

        if (status !== undefined) {
            updates.push(`status = $${paramIndex++}`);
            values.push(status);
        }
        if (processingStage !== undefined) {
            updates.push(`processing_stage = $${paramIndex++}`);
            values.push(processingStage);
        }
        if (processingProgress !== undefined) {
            updates.push(`processing_progress = $${paramIndex++}`);
            values.push(processingProgress);
        }
        if (extractedText !== undefined) {
            updates.push(`extracted_text = $${paramIndex++}`);
            values.push(extractedText);
        }
        if (markdownContent !== undefined) {
            updates.push(`markdown_content = $${paramIndex++}`);
            values.push(markdownContent);
        }
        if (transcript !== undefined) {
            updates.push(`transcript = $${paramIndex++}`);
            values.push(transcript);
        }
        if (aiSummary !== undefined) {
            updates.push(`ai_summary = $${paramIndex++}`);
            values.push(aiSummary);
        }
        if (entitiesExtracted !== undefined) {
            updates.push(`entities_extracted = $${paramIndex++}`);
            values.push(JSON.stringify(entitiesExtracted));
        }
        if (graphIngested !== undefined) {
            updates.push(`graph_ingested = $${paramIndex++}`);
            values.push(graphIngested);
        }
        if (errorMessage !== undefined) {
            updates.push(`error_message = $${paramIndex++}`);
            values.push(errorMessage);
        }

        // Update timestamps
        if (status === 'processing') {
            updates.push(`processing_started_at = NOW()`);
        }
        if (status === 'completed' || status === 'error') {
            updates.push(`processing_completed_at = NOW()`);
        }

        values.push(fileId, authority.profileId); // Last params for authority-scoped WHERE clause

        const result = await pool.query(
            `UPDATE received_data SET ${updates.join(', ')} WHERE id = $${paramIndex} AND profile_id = $${paramIndex + 1} RETURNING *`,
            values
        );

        if (result.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'File not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({
            success: true,
            file: result.rows[0],
        });
    } catch (error) {
        console.error('Failed to update file:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to update file' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/upload - Delete an individual file
 */
export async function DELETE(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    const searchParams = request.nextUrl.searchParams;
    const fileId = searchParams.get('fileId');

    if (!fileId) {
        return NextResponse.json(
            { success: false, error: 'fileId is required' },
            { status: 400 }
        );
    }

    try {
        // Get file path before deleting from DB
        const fileResult = await pool.query(
            'SELECT file_path FROM received_data WHERE id = $1 AND profile_id = $2',
            [fileId, authority.profileId]
        );

        if (fileResult.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'File not found' },
                { status: 404 }
            );
        }

        const filePath = fileResult.rows[0].file_path;

        // Delete from database
        // Try to delete the physical file
        if (filePath) {
            try {
                await unlink(filePath);
            } catch (fsError: any) {
                // File may not exist on disk — that's OK
                if (fsError?.code !== 'ENOENT') throw fsError;
            }
        }

        await pool.query('DELETE FROM received_data WHERE id = $1 AND profile_id = $2', [fileId, authority.profileId]);

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('Failed to delete file:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to delete file' },
            { status: 500 }
        );
    }
}

// Utility functions
function categorizeFile(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    if (['pdf'].includes(ext)) return 'pdf';
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext)) return 'image';
    if (['xlsx', 'xls', 'csv', 'ods'].includes(ext)) return 'spreadsheet';
    if (['mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac'].includes(ext)) return 'audio';
    if (['mp4', 'avi', 'mkv', 'mov', 'webm'].includes(ext)) return 'video';
    if (['doc', 'docx', 'txt', 'rtf', 'md'].includes(ext)) return 'document';
    if (['json', 'xml', 'html', 'htm'].includes(ext)) return 'data';
    return 'other';
}

function getMimeType(filename: string): string {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    const mimeTypes: Record<string, string> = {
        pdf: 'application/pdf',
        jpg: 'image/jpeg',
        jpeg: 'image/jpeg',
        png: 'image/png',
        gif: 'image/gif',
        csv: 'text/csv',
        xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        xls: 'application/vnd.ms-excel',
        txt: 'text/plain',
        json: 'application/json',
        xml: 'application/xml',
        mp3: 'audio/mpeg',
        wav: 'audio/wav',
        m4a: 'audio/mp4',
        mp4: 'video/mp4',
        doc: 'application/msword',
        docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    };
    return mimeTypes[ext] || 'application/octet-stream';
}
