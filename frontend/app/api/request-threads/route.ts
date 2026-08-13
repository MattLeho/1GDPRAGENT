import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { RequestService } from '@/lib/requests/service';

const requests = new RequestService();

export async function GET(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const { searchParams } = new URL(request.url);
        const company = searchParams.get('company');
        const threadId = searchParams.get('threadId');
        if (!company && !threadId) {
            return NextResponse.json({ success: false, error: 'Company or threadId required' }, { status: 400 });
        }
        const thread = await requests.getThread(authority.profileId, { company, threadId });
        return NextResponse.json({ success: true, thread, exists: thread !== null });
    } catch (error) {
        console.error('[Request Threads] GET error:', error);
        return NextResponse.json({ success: false, error: 'Failed to fetch thread' }, { status: 500 });
    }
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json() as Record<string, unknown>;
        if (typeof body.company !== 'string' || !body.company.trim()) {
            return NextResponse.json({ success: false, error: 'Company is required' }, { status: 400 });
        }
        if (typeof body.action !== 'string' || !body.action.trim()) {
            return NextResponse.json({ success: false, error: 'Action is required' }, { status: 400 });
        }
        const thread = await requests.updateThread(authority.profileId, authority.userId, {
            company: body.company,
            domain: typeof body.domain === 'string' ? body.domain : null,
            action: body.action,
            data: body.data && typeof body.data === 'object' ? body.data as Record<string, unknown> : {},
            requestId: typeof body.requestId === 'string' ? body.requestId : null,
        });
        if (!thread) {
            return NextResponse.json({ success: false, error: 'Request not found' }, { status: 404 });
        }
        return NextResponse.json({ success: true, thread, threadId: thread.thread_id });
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to update thread';
        const status = /canonical request link/.test(message) ? 409 : /Unknown request-thread action/.test(message) ? 400 : 500;
        if (status === 500) console.error('[Request Threads] POST error:', error);
        return NextResponse.json({ success: false, error: status === 500 ? 'Failed to update thread' : message }, { status });
    }
}
