import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Proxy to protect dashboard routes
 */
export function proxy(request: NextRequest) {
    // Check for session cookie
    const session = request.cookies.get('gdpr-session');

    // If accessing dashboard routes without session, redirect to login
    if (request.nextUrl.pathname.startsWith('/dashboard') || request.nextUrl.pathname.startsWith('/api/connectors') || request.nextUrl.pathname.startsWith('/api/retention')) {
        if (!session) {
            if (request.nextUrl.pathname.startsWith('/api/')) {
                return NextResponse.json({ detail: 'Authentication required' }, { status: 401 });
            }
            return NextResponse.redirect(new URL('/login', request.url));
        }
    }

    // If accessing login with active session, redirect to dashboard
    if (request.nextUrl.pathname === '/login') {
        if (session) {
            return NextResponse.redirect(new URL('/dashboard/home', request.url));
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: ['/dashboard/:path*', '/login', '/api/connectors/:path*', '/api/retention/:path*'],
};
