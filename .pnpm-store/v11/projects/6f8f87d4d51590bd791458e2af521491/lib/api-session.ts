import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createHash, createHmac, randomUUID } from 'node:crypto';
import { pool } from './db';
import {
  clearedSessionCookieOptions,
  SESSION_COOKIE_NAME,
  SessionAuthority,
  verifySessionToken,
} from './auth-session';

export type SessionFailureCode =
  | 'AUTHENTICATION_REQUIRED'
  | 'SESSION_INVALID'
  | 'SESSION_BINDING_INVALID'
  | 'SESSION_VALIDATION_UNAVAILABLE';

export type CsrfFailureCode = 'CSRF_ORIGIN_MISMATCH' | 'CSRF_REQUIRED';

export type SessionResolution =
  | { ok: true; authority: SessionAuthority }
  | { ok: false; code: SessionFailureCode; message: string; status: 401 | 503; clearCookie: boolean };

export class SessionAuthorityError extends Error {
  constructor(
    public readonly code: SessionFailureCode,
    public readonly status: 401 | 503,
    message?: string,
  ) {
    super(message ?? (code === 'AUTHENTICATION_REQUIRED' ? 'Authentication required' :
      code === 'SESSION_VALIDATION_UNAVAILABLE' ? 'Session could not be validated' :
        'Session is invalid or expired'));
    this.name = 'SessionAuthorityError';
  }

  toJSON() {
    return { error: { code: this.code, message: this.message } };
  }
}

export async function resolveSessionAuthority(token: string | undefined): Promise<SessionResolution> {
  if (!token) {
    return { ok: false, code: 'AUTHENTICATION_REQUIRED', message: 'Authentication required', status: 401, clearCookie: false };
  }

  let authority: SessionAuthority | null;
  try {
    authority = verifySessionToken(token);
  } catch (error) {
    console.error('[Session] Token verification is unavailable:', error);
    return {
      ok: false,
      code: 'SESSION_VALIDATION_UNAVAILABLE',
      message: 'Session could not be validated',
      status: 503,
      clearCookie: false,
    };
  }
  if (!authority) {
    return { ok: false, code: 'SESSION_INVALID', message: 'Session is invalid or expired', status: 401, clearCookie: true };
  }

  try {
    const result = await pool.query(
      `SELECT up.id
         FROM user_profiles up
         INNER JOIN profiles p ON p.id = up.default_profile_id
        WHERE up.id = $1 AND up.default_profile_id = $2 AND p.id = $2`,
      [authority.userId, authority.profileId],
    );
    if (result.rowCount !== 1) {
      return {
        ok: false,
        code: 'SESSION_BINDING_INVALID',
        message: 'Session account or profile no longer exists',
        status: 401,
        clearCookie: true,
      };
    }
    return { ok: true, authority };
  } catch (error) {
    console.error('[Session] Authority validation failed:', error);
    return {
      ok: false,
      code: 'SESSION_VALIDATION_UNAVAILABLE',
      message: 'Session could not be validated',
      status: 503,
      clearCookie: false,
    };
  }
}

export function sessionErrorResponse(failure: Extract<SessionResolution, { ok: false }>): NextResponse {
  const response = NextResponse.json(
    { success: false, error: { code: failure.code, message: failure.message }, detail: failure.message },
    { status: failure.status },
  );
  if (failure.clearCookie) {
    response.cookies.set(SESSION_COOKIE_NAME, '', clearedSessionCookieOptions());
  }
  return response;
}

function csrfErrorResponse(code: CsrfFailureCode, message: string): NextResponse {
  return NextResponse.json(
    { success: false, error: { code, message }, detail: message },
    { status: 403 },
  );
}

/**
 * Protect browser mutations. When Origin is unavailable, only the browser's explicit
 * Sec-Fetch-Site: same-origin signal is accepted; non-browser clients must send Origin.
 */
export function enforceSameOriginMutation(request: NextRequest): NextResponse | null {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method.toUpperCase())) return null;

  const origin = request.headers.get('origin');
  if (origin) {
    try {
      const host = request.headers.get('host')?.trim();
      const forwardedProtocol = request.headers.get('x-forwarded-proto')?.split(',', 1)[0]?.trim();
      const protocol = forwardedProtocol || request.nextUrl.protocol.replace(/:$/, '');
      if (!['http', 'https'].includes(protocol)) {
        return csrfErrorResponse('CSRF_ORIGIN_MISMATCH', 'Mutation request protocol is invalid');
      }
      const effectiveOrigin = host ? new URL(`${protocol}://${host}`).origin : request.nextUrl.origin;
      const allowedOrigins = new Set([effectiveOrigin]);
      if (process.env.NEXT_PUBLIC_APP_URL) {
        allowedOrigins.add(new URL(process.env.NEXT_PUBLIC_APP_URL).origin);
      }
      if (!allowedOrigins.has(new URL(origin).origin)) {
        return csrfErrorResponse('CSRF_ORIGIN_MISMATCH', 'Mutation origin does not match this application');
      }
    } catch {
      return csrfErrorResponse('CSRF_ORIGIN_MISMATCH', 'Mutation origin is invalid');
    }
  } else if (request.headers.get('sec-fetch-site') !== 'same-origin') {
    return csrfErrorResponse('CSRF_ORIGIN_MISMATCH', 'A same-origin browser request is required');
  }

  const contentType = request.headers.get('content-type')?.toLowerCase() ?? '';
  const fetchMode = request.headers.get('sec-fetch-mode');
  const isJsonOrFetch = contentType.includes('application/json') || (fetchMode !== null && fetchMode !== 'navigate');
  if (isJsonOrFetch && request.headers.get('x-gdpr-csrf') !== '1') {
    return csrfErrorResponse('CSRF_REQUIRED', 'The CSRF request header is required');
  }
  return null;
}

export async function requireApiSession(request: NextRequest): Promise<SessionAuthority | NextResponse> {
  const resolution = await resolveSessionAuthority(request.cookies.get(SESSION_COOKIE_NAME)?.value);
  if (!resolution.ok) return sessionErrorResponse(resolution);
  const csrfFailure = enforceSameOriginMutation(request);
  return csrfFailure ?? resolution.authority;
}

/** Resolve canonical authority in a Server Component or Server Action without fabricating a request. */
export async function requireServerSessionAuthority(): Promise<SessionAuthority> {
  const cookieStore = await cookies();
  const resolution = await resolveSessionAuthority(cookieStore.get(SESSION_COOKIE_NAME)?.value);
  if (resolution.ok) return resolution.authority;
  if (resolution.clearCookie) {
    try {
      cookieStore.set(SESSION_COOKIE_NAME, '', clearedSessionCookieOptions());
    } catch {
      // Server Components cannot mutate cookies. Dashboard proxy/route handlers clear it;
      // Server Actions can clear it here. Authority still fails closed in both contexts.
    }
  }
  throw new SessionAuthorityError(resolution.code, resolution.status, resolution.message);
}

const INTERNAL_AUTHORITY_VERSION = 'v1';

function rfc3986Encode(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, character =>
    `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
  );
}

export function canonicalIntelligenceTarget(target: string): { path: string; query: string } {
  const url = new URL(target, 'http://internal.invalid');
  const path = url.pathname.split('/').map(segment => rfc3986Encode(decodeURIComponent(segment))).join('/') || '/';
  const pairs = Array.from(url.searchParams.entries())
    .map(([key, value]) => [rfc3986Encode(key), rfc3986Encode(value)] as const)
    .sort(([leftKey, leftValue], [rightKey, rightValue]) =>
      leftKey < rightKey ? -1 : leftKey > rightKey ? 1 : leftValue < rightValue ? -1 : leftValue > rightValue ? 1 : 0,
    );
  return { path, query: pairs.map(([key, value]) => `${key}=${value}`).join('&') };
}

export function intelligenceAuthorityHeaders(
  profileId: string,
  target: string,
  method = 'GET',
  contentType = 'application/json',
  timestamp = Math.floor(Date.now() / 1000),
  nonce: string = randomUUID(),
  body: string | Uint8Array = '',
): Record<string, string> {
  const key = process.env.INTERNAL_API_KEY;
  if (!key) throw new Error('INTERNAL_API_KEY is required');
  const canonicalProfileId = profileId.toLowerCase();
  const { path, query } = canonicalIntelligenceTarget(target);
  const bodyDigest = createHash('sha256').update(body).digest('hex');
  const canonicalContentType = contentType.trim().toLowerCase();
  const payload = [INTERNAL_AUTHORITY_VERSION, String(timestamp), nonce, method.toUpperCase(), path, query, canonicalProfileId, canonicalContentType, bodyDigest].join('\n');
  return {
    'content-type': canonicalContentType,
    'x-gdpr-content-sha256': bodyDigest,
    'x-gdpr-internal-key': createHmac('sha256', key).update(payload, 'utf8').digest('hex'),
    'x-gdpr-internal-version': INTERNAL_AUTHORITY_VERSION,
    'x-gdpr-internal-timestamp': String(timestamp),
    'x-gdpr-internal-nonce': nonce,
    'x-gdpr-profile-id': canonicalProfileId,
  };
}
