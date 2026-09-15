import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

/**
 * DELETE /api/requests/[id] — Cancel a request while retaining its audit record.
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

        if (!await requests.cancel(authority.profileId, id, `user:${authority.userId}`)) {
            return NextResponse.json(
                { success: false, error: 'Request not found' },
                { status: 404 }
            );
        }

        return NextResponse.json({
            success: true,
            message: `Request ${id} cancelled; its evidence was retained`,
        });
    } catch (error) {
        console.error('Cancel request error:', error);
        return NextResponse.json(
            { success: false, error: 'Failed to cancel request' },
            { status: 500 }
        );
    }
}
