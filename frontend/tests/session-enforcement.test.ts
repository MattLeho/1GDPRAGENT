import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest, NextResponse } from 'next/server';

vi.mock('../lib/db', () => ({ pool: { query: vi.fn() } }));

import { pool } from '../lib/db';
import { createSessionToken, SESSION_COOKIE_NAME } from '../lib/auth-session';
import { enforceSameOriginMutation, requireApiSession } from '../lib/api-session';
import { proxy } from '../proxy';

const query = vi.mocked(pool.query);
const now = Date.now();

function request(path: string, token?: string) {
  const headers = new Headers();
  if (token !== undefined) headers.set('cookie', `${SESSION_COOKIE_NAME}=${token}`);
  return new NextRequest(`http://localhost:3000${path}`, { headers });
}

function mutation(headers: Record<string, string> = {}) {
  return new NextRequest('http://localhost:3000/api/protected', {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...headers },
  });
}

beforeEach(() => {
  process.env.SESSION_SIGNING_KEY = 'r1-enforcement-test-key';
  query.mockReset();
});

afterEach(() => {
  delete process.env.SESSION_SIGNING_KEY;
});

describe('API session enforcement', () => {
  it('returns a structured 401 when authentication is absent', async () => {
    const result = await requireApiSession(request('/api/protected'));
    expect(result).toBeInstanceOf(NextResponse);
    const response = result as NextResponse;
    expect(response.status).toBe(401);
    expect(await response.json()).toMatchObject({
      error: { code: 'AUTHENTICATION_REQUIRED', message: 'Authentication required' },
    });
  });

  it('clears a malformed session cookie', async () => {
    const result = await requireApiSession(request('/api/protected', 'malformed')) as NextResponse;
    expect(result.status).toBe(401);
    expect(result.headers.get('set-cookie')).toContain(`${SESSION_COOKIE_NAME}=`);
    expect(result.headers.get('set-cookie')).toContain('Max-Age=0');
  });

  it('returns the complete authority only after exact user/profile binding', async () => {
    query.mockResolvedValueOnce({ rowCount: 1, rows: [{ id: 'user-a' }] } as never);
    const token = createSessionToken('user-a', 'profile-a', now, now + 60_000);
    await expect(requireApiSession(request('/api/protected', token))).resolves.toEqual({
      userId: 'user-a', profileId: 'profile-a', issuedAt: now, expiresAt: now + 60_000,
    });
    expect(query).toHaveBeenCalledWith(expect.stringContaining('up.default_profile_id = $2'), ['user-a', 'profile-a']);
  });

  it('rejects and clears a token whose database binding no longer exists', async () => {
    query.mockResolvedValueOnce({ rowCount: 0, rows: [] } as never);
    const token = createSessionToken('user-a', 'profile-a', now, now + 60_000);
    const result = await requireApiSession(request('/api/protected', token)) as NextResponse;
    expect(result.status).toBe(401);
    expect(await result.json()).toMatchObject({ error: { code: 'SESSION_BINDING_INVALID' } });
    expect(result.headers.get('set-cookie')).toContain('Max-Age=0');
  });
});

describe('same-origin mutation enforcement', () => {
  it('rejects foreign origins with a structured 403', async () => {
    const response = enforceSameOriginMutation(mutation({
      origin: 'https://attacker.example',
      'x-gdpr-csrf': '1',
    })) as NextResponse;
    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ error: { code: 'CSRF_ORIGIN_MISMATCH' } });
  });

  it('requires the CSRF header for a same-origin JSON mutation', async () => {
    const response = enforceSameOriginMutation(mutation({ origin: 'http://localhost:3000' })) as NextResponse;
    expect(response.status).toBe(403);
    expect(await response.json()).toMatchObject({ error: { code: 'CSRF_REQUIRED' } });
  });

  it('accepts exact same-origin and the narrow Sec-Fetch-Site fallback', () => {
    expect(enforceSameOriginMutation(mutation({
      origin: 'http://localhost:3000', 'x-gdpr-csrf': '1',
    }))).toBeNull();
    expect(enforceSameOriginMutation(mutation({
      'sec-fetch-site': 'same-origin', 'x-gdpr-csrf': '1',
    }))).toBeNull();
  });
});

describe('pre-render dashboard and login enforcement', () => {
  it('redirects a malformed dashboard session with a reason and clears it', async () => {
    const response = await proxy(request('/dashboard/home', 'malformed'));
    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe('http://localhost:3000/login?reason=session_invalid');
    expect(response.headers.get('set-cookie')).toContain('Max-Age=0');
  });

  it('does not redirect login merely because a cookie is present', async () => {
    const response = await proxy(request('/login', 'malformed'));
    expect(response.headers.get('location')).toBeNull();
    expect(response.headers.get('set-cookie')).toContain('Max-Age=0');
  });

  it('redirects login only after token and database authority verification', async () => {
    query.mockResolvedValueOnce({ rowCount: 1, rows: [{ id: 'user-a' }] } as never);
    const token = createSessionToken('user-a', 'profile-a', now, now + 60_000);
    const response = await proxy(request('/login', token));
    expect(response.headers.get('location')).toBe('http://localhost:3000/dashboard/home');
  });
});
