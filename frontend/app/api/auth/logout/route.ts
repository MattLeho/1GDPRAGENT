import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { clearedSessionCookieOptions, SESSION_COOKIE_NAME } from '@/lib/auth-session';
import { enforceSameOriginMutation } from '@/lib/api-session';

/**
 * POST /api/auth/logout - Logout and clear session
 */
export async function POST(request: NextRequest) {
    try {
        const csrfFailure = enforceSameOriginMutation(request);
        if (csrfFailure) return csrfFailure;
        (await cookies()).set(SESSION_COOKIE_NAME, '', clearedSessionCookieOptions());

        return NextResponse.json({
            success: true,
            message: 'Logged out successfully',
        });
    } catch (error) {
        console.error('Logout failed:', error);
        return NextResponse.json(
            { success: false, error: 'Logout failed' },
            { status: 500 }
        );
    }
}
