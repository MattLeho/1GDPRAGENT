import { NextResponse, NextRequest } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { testImapConnection as testImap } from '@/lib/n8n-client';

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    try {
        const body = await request.json();
        const { email, host, port = 993, password } = body;

        if (!email || !host || !password) {
            return NextResponse.json(
                { success: false, message: 'Email, host, and password are required' },
                { status: 400 }
            );
        }

        // Call N8N Inbox Monitor Agent to test connection
        const result = await testImap({ email, host, port, password });

        if (!result.success) {
            return NextResponse.json({
                success: false,
                message: result.error || 'IMAP connection test failed',
            });
        }

        return NextResponse.json({
            success: true,
            message: result.data?.connected
                ? `Connected successfully! Found ${result.data.mailboxCount || 0} mailboxes.`
                : 'Connection test completed',
            mailboxCount: result.data?.mailboxCount,
        });

    } catch (error) {
        console.error('IMAP test endpoint error:', error);
        return NextResponse.json(
            { success: false, message: 'Internal server error' },
            { status: 500 }
        );
    }
}
