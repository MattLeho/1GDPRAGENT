import { NextResponse, NextRequest } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { pool } from '@/lib/db';

const UPLOAD_DIR = path.join(process.cwd(), 'uploads', 'id_documents');

async function ensureUploadDir() {
    if (!existsSync(UPLOAD_DIR)) {
        await mkdir(UPLOAD_DIR, { recursive: true });
    }
}

/**
 * Simple client-side redaction for demo - in production, use proper server-side image processing
 */
async function createCensoredVersion(originalPath: string, documentType: string): Promise<string | null> {
    // For now, return null and handle client-side
    // In production, use sharp or similar to actually redact the image
    return null;
}

/**
 * GET /api/settings/id-documents - Get all ID documents
 */
export async function GET() {
    try {
        const result = await pool.query(
            `SELECT id, document_type, file_name, file_url, censored_url, uploaded_at
             FROM id_documents
             ORDER BY uploaded_at DESC`
        );

        return NextResponse.json({
            success: true,
            documents: result.rows.map(row => ({
                id: row.id,
                documentType: row.document_type,
                fileName: row.file_name,
                fileUrl: row.file_url,
                censoredUrl: row.censored_url,
                uploadedAt: row.uploaded_at,
            })),
        });
    } catch (error) {
        console.error('Failed to get documents:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to load documents' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/settings/id-documents - Upload a new ID document
 */
export async function POST(request: NextRequest) {
    try {
        const formData = await request.formData();
        const file = formData.get('file') as File;
        const documentType = formData.get('documentType') as string;

        if (!file || !documentType) {
            return NextResponse.json(
                { success: false, error: 'File and document type are required' },
                { status: 400 }
            );
        }

        await ensureUploadDir();

        // Save original file
        const bytes = await file.arrayBuffer();
        const buffer = Buffer.from(bytes);

        const ext = path.extname(file.name);
        const filename = `${documentType}_${Date.now()}${ext}`;
        const filepath = path.join(UPLOAD_DIR, filename);

        await writeFile(filepath, buffer);

        const fileUrl = `/uploads/id_documents/${filename}`;

        // Create censored version (placeholder - would use actual image processing)
        const censoredUrl = await createCensoredVersion(filepath, documentType);

        // Insert into database
        const result = await pool.query(
            `INSERT INTO id_documents (document_type, file_name, file_url, censored_url)
             VALUES ($1, $2, $3, $4)
             RETURNING id, document_type, file_name, file_url, censored_url, uploaded_at`,
            [documentType, file.name, fileUrl, censoredUrl]
        );

        return NextResponse.json({
            success: true,
            document: {
                id: result.rows[0].id,
                documentType: result.rows[0].document_type,
                fileName: result.rows[0].file_name,
                fileUrl: result.rows[0].file_url,
                censoredUrl: result.rows[0].censored_url,
                uploadedAt: result.rows[0].uploaded_at,
            },
        });
    } catch (error) {
        console.error('Failed to upload document:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to upload document' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/settings/id-documents - Delete an ID document
 */
export async function DELETE(request: NextRequest) {
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        if (!id) {
            return NextResponse.json(
                { success: false, error: 'Document ID is required' },
                { status: 400 }
            );
        }

        await pool.query('DELETE FROM id_documents WHERE id = $1', [id]);

        return NextResponse.json({
            success: true,
            message: 'Document deleted successfully',
        });
    } catch (error) {
        console.error('Failed to delete document:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to delete document' },
            { status: 500 }
        );
    }
}
