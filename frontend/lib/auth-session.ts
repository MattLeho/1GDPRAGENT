import { createHmac, timingSafeEqual } from 'node:crypto';

export interface SessionAuthority {
  userId: string;
  profileId: string;
  issuedAt: number;
  expiresAt: number;
}

export const SESSION_COOKIE_NAME = 'gdpr-session';
export const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const TOKEN_VERSION = 'v1';

function signingKey(): string {
  const key = process.env.SESSION_SIGNING_KEY;
  if (!key) throw new Error('SESSION_SIGNING_KEY is required');
  return key;
}

function signature(version: string, payload: string): string {
  return createHmac('sha256', signingKey()).update(`${version}.${payload}`).digest('base64url');
}

function isAuthority(value: unknown): value is SessionAuthority {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<SessionAuthority>;
  return (
    typeof candidate.userId === 'string' && candidate.userId.length > 0 &&
    typeof candidate.profileId === 'string' && candidate.profileId.length > 0 &&
    typeof candidate.issuedAt === 'number' && Number.isSafeInteger(candidate.issuedAt) &&
    typeof candidate.expiresAt === 'number' && Number.isSafeInteger(candidate.expiresAt)
  );
}

export function createSessionToken(
  userId: string,
  profileId: string,
  issuedAt = Date.now(),
  expiresAt = issuedAt + SESSION_TTL_MS,
): string {
  const authority: SessionAuthority = { userId, profileId, issuedAt, expiresAt };
  if (!isAuthority(authority) || expiresAt <= issuedAt || expiresAt - issuedAt > SESSION_TTL_MS) {
    throw new Error('Invalid session authority');
  }
  const payload = Buffer.from(JSON.stringify(authority), 'utf8').toString('base64url');
  return `${TOKEN_VERSION}.${payload}.${signature(TOKEN_VERSION, payload)}`;
}

export function verifySessionToken(token: string, now = Date.now()): SessionAuthority | null {
  const [version, payload, supplied, ...extra] = token.split('.');
  if (version !== TOKEN_VERSION || !payload || !supplied || extra.length) return null;

  const expected = signature(version, payload);
  const suppliedBytes = Buffer.from(supplied, 'utf8');
  const expectedBytes = Buffer.from(expected, 'utf8');
  if (suppliedBytes.length !== expectedBytes.length || !timingSafeEqual(suppliedBytes, expectedBytes)) {
    return null;
  }

  try {
    const authority: unknown = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    if (!isAuthority(authority)) return null;
    if (authority.issuedAt > now || authority.expiresAt <= now) return null;
    if (authority.expiresAt <= authority.issuedAt || authority.expiresAt - authority.issuedAt > SESSION_TTL_MS) {
      return null;
    }
    return authority;
  } catch {
    return null;
  }
}

export function sessionCookieOptions(expiresAt: number, now = Date.now()) {
  return {
    httpOnly: true as const,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    path: '/',
    maxAge: Math.max(0, Math.ceil((expiresAt - now) / 1000)),
    expires: new Date(expiresAt),
  };
}

export function clearedSessionCookieOptions() {
  return {
    httpOnly: true as const,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    path: '/',
    maxAge: 0,
    expires: new Date(0),
  };
}
