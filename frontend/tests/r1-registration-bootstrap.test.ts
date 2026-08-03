import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

const state = vi.hoisted(() => ({ queries: [] as string[], existing: true }));
const client = vi.hoisted(() => ({
  query: vi.fn(async (sql: string) => {
    state.queries.push(sql);
    if (sql.includes('SELECT 1 FROM user_profiles')) return { rowCount: state.existing ? 1 : 0, rows: state.existing ? [{}] : [] };
    if (sql.includes('INSERT INTO profiles')) return { rowCount: 1, rows: [{ id: 'profile-a' }] };
    if (sql.includes('INSERT INTO user_profiles')) return { rowCount: 1, rows: [{ id: 'user-a', username: 'owner', default_profile_id: 'profile-a' }] };
    return { rowCount: null, rows: [] };
  }),
  release: vi.fn(),
}));

vi.mock('../lib/db', () => ({ pool: { connect: vi.fn(async () => client) } }));
vi.mock('bcryptjs', () => ({ default: { hash: vi.fn(async () => 'hash') } }));
vi.mock('next/headers', () => ({ cookies: vi.fn(async () => ({ set: vi.fn() })) }));
vi.mock('../lib/auth-session', () => ({
  createSessionToken: vi.fn(() => 'v1.payload.signature'), SESSION_COOKIE_NAME: 'gdpr-session',
  SESSION_TTL_MS: 60_000, sessionCookieOptions: vi.fn(() => ({})),
}));

import { POST } from '../app/api/auth/register/route';

function registrationRequest() {
  return new NextRequest('http://localhost/api/auth/register', {
    method: 'POST',
    headers: { origin: 'http://localhost', 'content-type': 'application/json', 'x-gdpr-csrf': '1' },
    body: JSON.stringify({ username: 'owner', password: 'long-enough-password' }),
  });
}

describe('bootstrap-only registration', () => {
  beforeEach(() => { state.queries = []; state.existing = true; client.query.mockClear(); client.release.mockClear(); });

  it('rejects registration once any account exists without creating another profile', async () => {
    const response = await POST(registrationRequest());
    expect(response.status).toBe(409);
    expect(state.queries.some(sql => sql.includes('INSERT INTO'))).toBe(false);
  });

  it('takes the transaction-scoped setup lock before checking and creating the initial account', async () => {
    state.existing = false;
    const response = await POST(registrationRequest());
    expect(response.status).toBe(200);
    const lock = state.queries.findIndex(sql => sql.includes('pg_advisory_xact_lock'));
    const existence = state.queries.findIndex(sql => sql.includes('SELECT 1 FROM user_profiles'));
    const create = state.queries.findIndex(sql => sql.includes('INSERT INTO profiles'));
    expect(lock).toBeGreaterThanOrEqual(0);
    expect(lock).toBeLessThan(existence);
    expect(existence).toBeLessThan(create);
  });
});
