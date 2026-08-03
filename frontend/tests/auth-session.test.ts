import { afterEach, describe, expect, it } from 'vitest';
import {
  createSessionToken,
  SESSION_TTL_MS,
  sessionCookieOptions,
  verifySessionToken,
} from '../lib/auth-session';

const originalSigningKey = process.env.SESSION_SIGNING_KEY;
const originalCredentialKey = process.env.CREDENTIALS_ENCRYPTION_KEY;
const now = 1_800_000_000_000;

afterEach(() => {
  if (originalSigningKey === undefined) delete process.env.SESSION_SIGNING_KEY;
  else process.env.SESSION_SIGNING_KEY = originalSigningKey;
  if (originalCredentialKey === undefined) delete process.env.CREDENTIALS_ENCRYPTION_KEY;
  else process.env.CREDENTIALS_ENCRYPTION_KEY = originalCredentialKey;
});

describe('session token contract', () => {
  it('accepts a valid versioned token and returns its embedded authority and expiry', () => {
    process.env.SESSION_SIGNING_KEY = 'r1-test-signing-key';
    const expiresAt = now + SESSION_TTL_MS;
    const token = createSessionToken('user-a', 'profile-a', now, expiresAt);

    expect(token.startsWith('v1.')).toBe(true);
    expect(verifySessionToken(token, now)).toEqual({
      userId: 'user-a',
      profileId: 'profile-a',
      issuedAt: now,
      expiresAt,
    });
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
    expect(payload.expiresAt).toBe(expiresAt);
  });

  it('rejects malformed tokens and unsupported versions', () => {
    process.env.SESSION_SIGNING_KEY = 'r1-test-signing-key';
    expect(verifySessionToken('not-a-token', now)).toBeNull();
    expect(verifySessionToken('v2.payload.signature', now)).toBeNull();
  });

  it('rejects signature mismatch and payload tampering', () => {
    process.env.SESSION_SIGNING_KEY = 'r1-test-signing-key';
    const token = createSessionToken('user-a', 'profile-a', now, now + 10_000);
    const [version, payload, signature] = token.split('.');
    const changedPayload = Buffer.from(JSON.stringify({
      userId: 'user-a', profileId: 'profile-b', issuedAt: now, expiresAt: now + 10_000,
    })).toString('base64url');
    expect(verifySessionToken(`${version}.${changedPayload}.${signature}`, now)).toBeNull();

    process.env.SESSION_SIGNING_KEY = 'different-signing-key';
    expect(verifySessionToken(`${version}.${payload}.${signature}`, now)).toBeNull();
  });

  it('rejects any future-issued token', () => {
    process.env.SESSION_SIGNING_KEY = 'r1-test-signing-key';
    const token = createSessionToken('user-a', 'profile-a', now + 1, now + 10_000);
    expect(verifySessionToken(token, now)).toBeNull();
  });

  it('rejects an expired token at the embedded expiry boundary', () => {
    process.env.SESSION_SIGNING_KEY = 'r1-test-signing-key';
    const token = createSessionToken('user-a', 'profile-a', now - 10_000, now);
    expect(verifySessionToken(token, now)).toBeNull();
  });

  it('uses only SESSION_SIGNING_KEY and never falls back to an encryption key', () => {
    delete process.env.SESSION_SIGNING_KEY;
    process.env.CREDENTIALS_ENCRYPTION_KEY = 'must-not-sign-sessions';
    expect(() => createSessionToken('user-a', 'profile-a', now, now + 10_000)).toThrow(
      'SESSION_SIGNING_KEY is required',
    );
  });

  it('aligns the bounded cookie lifetime and expiry with the authority', () => {
    const expiresAt = now + SESSION_TTL_MS;
    expect(sessionCookieOptions(expiresAt, now)).toMatchObject({
      httpOnly: true,
      sameSite: 'lax',
      path: '/',
      maxAge: SESSION_TTL_MS / 1000,
      expires: new Date(expiresAt),
    });
  });
});
