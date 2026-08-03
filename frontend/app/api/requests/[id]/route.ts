import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

/**
 * DELETE /api/requests/[id] — Delete a request and all associated data
 * 
 * Child rows are removed by canonical foreign-key cascades in one transaction.
 */
export async function DELETE(
    _request: NextRequest,
    { params }: { params: Promise<{ id: string }> }
) {
    const authority = await requireApiSession(_request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { id } = await params;

        if (!id) {
            return NextResponse.json(
                { success: false, error: 'Request ID is required' },
                { status: 400 }
            );
        }

        if (!await requests.delete(authority.profileId, id)) {
            return NextResponse.json(
                { success: false, error: 'Request not found' },
                { status: 404 }
            );
        }

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
