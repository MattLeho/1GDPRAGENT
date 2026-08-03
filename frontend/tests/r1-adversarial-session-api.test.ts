import { createHash, createHmac } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const mocks = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock('@/lib/db', () => ({ pool: { query: mocks.query } }));

import {
  enforceSameOriginMutation,
  intelligenceAuthorityHeaders,
  requireApiSession,
  resolveSessionAuthority,
} from '@/lib/api-session';
import { createSessionToken, SESSION_TTL_MS } from '@/lib/auth-session';

const now = 1_800_000_000_000;
const signingKey = 'r1-adversarial-session-key';
const internalKey = 'r1-adversarial-internal-key';

function request(method = 'GET', headers: Record<string, string> = {}, token?: string) {
  const allHeaders = new Headers(headers);
  if (token) allHeaders.set('cookie', `gdpr-session=${token}`);
  return new NextRequest('https://gdpr.test/api/sensitive', { method, headers: allHeaders });
}

describe('R1 adversarial session authority', () => {
  beforeEach(() => {
    process.env.SESSION_SIGNING_KEY = signingKey;
    process.env.INTERNAL_API_KEY = internalKey;
    mocks.query.mockReset();
  });

  afterEach(() => vi.restoreAllMocks());

  it('accepts a current token only after the exact user/profile binding exists', async () => {
    const token = createSessionToken('user-a', 'profile-a', now, now + 10_000);
    mocks.query.mockResolvedValue({ rowCount: 1, rows: [{ id: 'user-a' }] });
    vi.spyOn(Date, 'now').mockReturnValue(now);

    await expect(resolveSessionAuthority(token)).resolves.toEqual({
      ok: true,
      authority: { userId: 'user-a', profileId: 'profile-a', issuedAt: now, expiresAt: now + 10_000 },
    });
    expect(mocks.query).toHaveBeenCalledWith(expect.stringMatching(/up\.id = \$1[\s\S]*default_profile_id = \$2/), ['user-a', 'profile-a']);
  });

  it.each([
    ['missing', () => undefined, 'AUTHENTICATION_REQUIRED', false],
    ['malformed', () => 'not-a-token', 'SESSION_INVALID', true],
    ['tampered', () => {
      const token = createSessionToken('user-a', 'profile-a', now, now + 10_000);
      return `${token.slice(0, -1)}${token.endsWith('a') ? 'b' : 'a'}`;
    }, 'SESSION_INVALID', true],
    ['expired', () => createSessionToken('user-a', 'profile-a', now - 20_000, now - 1), 'SESSION_INVALID', true],
    ['future', () => createSessionToken('user-a', 'profile-a', now + 1, now + 10_000), 'SESSION_INVALID', true],
  ])('rejects a %s session deterministically', async (_label, tokenFactory, code, clearCookie) => {
    vi.spyOn(Date, 'now').mockReturnValue(now);
    await expect(resolveSessionAuthority(tokenFactory())).resolves.toMatchObject({ ok: false, code, status: 401, clearCookie });
    expect(mocks.query).not.toHaveBeenCalled();
  });

  it.each(['deleted-user', 'deleted-profile', 'mismatched-profile'])('rejects a %s binding without revealing which row is absent', async () => {
    const token = createSessionToken('user-a', 'profile-a', now, now + 10_000);
    vi.spyOn(Date, 'now').mockReturnValue(now);
    mocks.query.mockResolvedValue({ rowCount: 0, rows: [] });
    await expect(resolveSessionAuthority(token)).resolves.toMatchObject({
      ok: false, code: 'SESSION_BINDING_INVALID', status: 401, clearCookie: true,
    });
  });

  it('returns a clearing Set-Cookie for an invalid token at the API boundary', async () => {
    const response = await requireApiSession(request('GET', {}, 'malformed'));
    expect(response).toBeInstanceOf(Response);
    const http = response as Response;
    expect(http.status).toBe(401);
    expect(http.headers.get('set-cookie')).toMatch(/gdpr-session=;.*Max-Age=0/i);
  });
});

describe('R1 adversarial browser mutation protection', () => {
  it('rejects a foreign Origin before route mutation code can run', async () => {
    const response = enforceSameOriginMutation(request('POST', {
      origin: 'https://attacker.invalid',
      'content-type': 'application/json',
      'x-gdpr-csrf': '1',
    }));
    expect(response?.status).toBe(403);
    await expect(response?.json()).resolves.toMatchObject({ error: { code: 'CSRF_ORIGIN_MISMATCH' } });
  });

  it('rejects a same-origin JSON mutation without the explicit CSRF marker', async () => {
    const response = enforceSameOriginMutation(request('PATCH', {
      origin: 'https://gdpr.test',
      'content-type': 'application/json',
    }));
    expect(response?.status).toBe(403);
    await expect(response?.json()).resolves.toMatchObject({ error: { code: 'CSRF_REQUIRED' } });
  });

  it('accepts same-origin mutation only with the marker', () => {
    expect(enforceSameOriginMutation(request('DELETE', {
      origin: 'https://gdpr.test',
      'x-gdpr-csrf': '1',
      'content-type': 'application/json',
    }))).toBeNull();
  });
});

describe('R1 internal caller authority generation', () => {
  it('binds signature to method, canonical target, profile, timestamp, and nonce', () => {
    const profile = '2D495690-80F4-45A6-973E-6F5A8F98EE12';
    const timestamp = 1_800_000_000;
    const nonce = 'nonce_for_adversarial_test_001';
    const headers = intelligenceAuthorityHeaders(profile, '/insights/evidence/a?z=2&a=1', 'GET', 'application/json', timestamp, nonce);
    const payload = ['v1', timestamp, nonce, 'GET', '/insights/evidence/a', 'a=1&z=2', profile.toLowerCase(), 'application/json', createHash('sha256').update('').digest('hex')].join('\n');
    expect(headers['x-gdpr-internal-key']).toBe(createHmac('sha256', internalKey).update(payload).digest('hex'));
    expect(headers['x-gdpr-profile-id']).toBe(profile.toLowerCase());
  });

  it('does not fall back to the session signing key', () => {
    delete process.env.INTERNAL_API_KEY;
    process.env.SESSION_SIGNING_KEY = 'must-not-authorize-internal-calls';
    expect(() => intelligenceAuthorityHeaders('profile-a', '/graph')).toThrow('INTERNAL_API_KEY is required');
  });

  it('prevents overlong session lifetime fabrication', () => {
    expect(() => createSessionToken('user-a', 'profile-a', now, now + SESSION_TTL_MS + 1)).toThrow('Invalid session authority');
  });
});
