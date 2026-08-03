import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { clearedSessionCookieOptions, SESSION_COOKIE_NAME } from './lib/auth-session';
import { resolveSessionAuthority } from './lib/api-session';

function redirectToLogin(request: NextRequest, reason: string, clearCookie: boolean) {
  const url = new URL('/login', request.url);
  url.searchParams.set('reason', reason);
  const response = NextResponse.redirect(url);
  if (clearCookie) response.cookies.set(SESSION_COOKIE_NAME, '', clearedSessionCookieOptions());
  return response;
}

export async function proxy(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;

  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    const resolution = await resolveSessionAuthority(token);
    if (!resolution.ok) {
      const reason = resolution.code === 'AUTHENTICATION_REQUIRED'
        ? 'authentication_required'
        : resolution.code === 'SESSION_VALIDATION_UNAVAILABLE'
          ? 'session_validation_unavailable'
          : 'session_invalid';
      return redirectToLogin(request, reason, resolution.clearCookie);
    }
  }

  if (request.nextUrl.pathname === '/login' && token) {
    const resolution = await resolveSessionAuthority(token);
    if (resolution.ok) return NextResponse.redirect(new URL('/dashboard/home', request.url));
    if (resolution.clearCookie) {
      const response = NextResponse.next();
      response.cookies.set(SESSION_COOKIE_NAME, '', clearedSessionCookieOptions());
      return response;
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/login'],
};
