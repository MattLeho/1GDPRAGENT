import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { writeFile, mkdir, unlink } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
import { pool } from '@/lib/db';

const UPLOAD_DIR = path.join(process.cwd(), 'uploads', 'id_documents');
const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;
const ALLOWED_DOCUMENT_TYPES = new Set(['passport', 'drivers_license', 'national_id', 'utility_bill']);
const ALLOWED_MIME_EXTENSIONS = new Map([
    ['application/pdf', '.pdf'], ['image/jpeg', '.jpg'], ['image/png', '.png'], ['image/webp', '.webp'],
]);

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
export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const result = await pool.query(
            `SELECT id, document_type, file_name, file_url, censored_url, uploaded_at
             FROM id_documents
             WHERE profile_id = $1
             ORDER BY uploaded_at DESC`
            , [authority.profileId]
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
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
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
        if (!ALLOWED_DOCUMENT_TYPES.has(documentType)) {
            return NextResponse.json({ success: false, error: 'Unsupported document type' }, { status: 400 });
        }
        const safeExtension = ALLOWED_MIME_EXTENSIONS.get(file.type);
        if (!safeExtension || file.size <= 0 || file.size > MAX_DOCUMENT_BYTES) {
            return NextResponse.json({ success: false, error: 'Only PDF, JPEG, PNG, or WebP files up to 10 MB are accepted' }, { status: 400 });
        }

        await ensureUploadDir();

        // Save original file
        const bytes = await file.arrayBuffer();
        const buffer = Buffer.from(bytes);

        const filename = `${randomUUID()}${safeExtension}`;
        const filepath = path.join(UPLOAD_DIR, filename);

        await writeFile(filepath, buffer);

        const fileUrl = `/uploads/id_documents/${filename}`;

        // Create censored version (placeholder - would use actual image processing)
        const censoredUrl = await createCensoredVersion(filepath, documentType);

        // Insert into database
        let result;
        try {
            result = await pool.query(
                `INSERT INTO id_documents (document_type, file_name, file_url, censored_url, profile_id)
                 VALUES ($1, $2, $3, $4, $5)
                 RETURNING id, document_type, file_name, file_url, censored_url, uploaded_at`,
                [documentType, path.basename(file.name), fileUrl, censoredUrl, authority.profileId]
            );
        } catch (error) {
            await unlink(filepath).catch(() => undefined);
            throw error;
        }

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
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get('id');

        if (!id) {
            return NextResponse.json(
                { success: false, error: 'Document ID is required' },
                { status: 400 }
            );
        }

        const owned = await pool.query(
            'SELECT id, file_url, censored_url FROM id_documents WHERE id = $1 AND profile_id = $2',
            [id, authority.profileId],
        );
        if (owned.rowCount !== 1) {
            return NextResponse.json({ success: false, error: 'Document not found' }, { status: 404 });
        }
        for (const url of [owned.rows[0].file_url, owned.rows[0].censored_url]) {
            if (!url) continue;
            const candidate = path.join(UPLOAD_DIR, path.basename(String(url)));
            try { await unlink(candidate); } catch (error: any) {
                if (error?.code !== 'ENOENT') throw error;
            }
        }
        await pool.query('DELETE FROM id_documents WHERE id = $1 AND profile_id = $2', [id, authority.profileId]);

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
