import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { writeFile, mkdir, rm } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
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
        const uploadedFiles: Array<{
            id: string;
            fileName: string;
            filePath: string;
            fileSize: number;
            fileType: string;
            category: string;
            status: string;
        }> = [];
        const databaseFiles: Array<{
            file_name:string;original_name:string;file_path:string;file_size_mb:number;file_type:string;category:string;
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

                        databaseFiles.push({file_name:sanitizedEntry,original_name:`${file.name}/${entryName}`,
                            file_path:entryPath,file_size_mb:entrySizeMb,file_type:entryMime,category:entryCategory});

                        uploadedFiles.push({
                            id: '',
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
                    databaseFiles.push({file_name:sanitizedName,original_name:file.name,file_path:filePath,
                        file_size_mb:fileSizeMb,file_type:file.type||'application/zip',category});
                    uploadedFiles.push({
                        id: '',
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

            databaseFiles.push({file_name:sanitizedName,original_name:file.name,file_path:filePath,
                file_size_mb:fileSizeMb,file_type:file.type||getMimeType(file.name),category});

            uploadedFiles.push({
                id: '',
                fileName: sanitizedName,
                filePath: filePath,
                fileSize: file.size,
                fileType: file.type || getMimeType(file.name),
                category: category,
                status: 'pending',
            });
        }

        const inserted = await requests.registerReceivedDataBatch(authority.profileId, requestId, databaseFiles);
        if (inserted.length !== uploadedFiles.length) throw new Error('Upload metadata registration was incomplete');
        inserted.forEach((row, index) => { uploadedFiles[index].id = row.id; });
        return NextResponse.json({
            success: true,
            batchId,
            files: uploadedFiles,
            totalFiles: uploadedFiles.length,
            totalSizeMb: uploadedFiles.reduce((sum, f) => sum + f.fileSize / (1024 * 1024), 0).toFixed(2),
        });
    } catch (error) {
        if (batchDir && batchDir.startsWith(`${UPLOAD_DIR}${path.sep}`)) {
            await rm(batchDir, { recursive: true, force: true }).catch(() => undefined);
        }
        console.error('Upload error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to upload files' },
            { status: 500 }
        );
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
        const rows = await requests.listReceivedData(authority.profileId, { fileId, requestId });

        return NextResponse.json({
            success: true,
            files: rows.map((row) => ({
                id: row.id,
                requestId: row.request_id,
                fileName: row.file_name,
                originalName: row.original_name,
                filePath: row.file_path,
                fileSizeMb: Number(row.file_size_mb) || 0,
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

        const file = await requests.updateReceivedData(authority.profileId, fileId, {
            status, processingStage, processingProgress, extractedText, markdownContent,
            transcript, aiSummary, entitiesExtracted, graphIngested, errorMessage,
        });

        if (!file) {
            return NextResponse.json(
                { success: false, error: 'File not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({
            success: true,
            file,
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
        const file = await requests.getOwnedReceivedData(authority.profileId, fileId);

        if (!file) {
            return NextResponse.json(
                { success: false, error: 'File not found' },
                { status: 404 }
            );
        }

        return NextResponse.json(
            { success: false, error: 'Received evidence is retained and cannot be permanently deleted' },
            { status: 409 },
        );

        /* Evidence retention is deliberate; no physical file or row is removed. */
        if (false) {
            try {
                await Promise.resolve();
            } catch (fsError: any) {
                // File may not exist on disk — that's OK
                if (fsError?.code !== 'ENOENT') throw fsError;
            }
        }

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
