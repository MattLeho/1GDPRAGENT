import { NextRequest, NextResponse } from 'next/server';
import { pool } from '@/lib/db';

/**
 * DELETE /api/requests/[id] — Delete a request and all associated data
 * 
 * Cascade deletes:
 * 1. request_chat_messages (FK: request_id)
 * 2. received_data / uploaded files (FK: request_id)
 * 3. access_requests (main record)
 */
export async function DELETE(
    _request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    try {
        const { id } = await params;

        if (!id) {
            return NextResponse.json(
                { success: false, error: 'Request ID is required' },
                { status: 400 }
            );
        }

        // Verify request exists
        const check = await pool.query(
            'SELECT id FROM access_requests WHERE id = $1',
            [id]
        );

        if (check.rows.length === 0) {
            return NextResponse.json(
                { success: false, error: 'Request not found' },
                { status: 404 }
            );
        }

        // Cascade delete in order (child tables first)
        await pool.query('DELETE FROM request_chat_messages WHERE request_id = $1', [id]);
        await pool.query('DELETE FROM received_data WHERE request_id = $1', [id]);

        // Delete from request_threads if it exists
        try {
            await pool.query('DELETE FROM request_threads WHERE request_id = $1', [id]);
        } catch {
            // Table may not exist yet, that's fine
        }

        // Delete the main request record
        await pool.query('DELETE FROM access_requests WHERE id = $1', [id]);

        return NextResponse.json({
            success: true,
            message: `Request ${id} and all associated data deleted`,
        });
    } catch (error) {
        console.error('Delete request error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to delete request' },
            { status: 500 }
        );
    }
}
