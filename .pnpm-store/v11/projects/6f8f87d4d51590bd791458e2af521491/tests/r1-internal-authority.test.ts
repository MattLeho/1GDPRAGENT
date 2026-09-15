import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createHash, createHmac } from 'node:crypto';

import { canonicalIntelligenceTarget, intelligenceAuthorityHeaders } from '../lib/api-session';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const secret = 'r1-test-internal-secret-with-sufficient-entropy';
const profileId = '12345678-1234-4abc-8def-1234567890ab';

describe('signed intelligence authority', () => {
  beforeEach(() => {
    process.env.INTERNAL_API_KEY = secret;
    vi.spyOn(Date, 'now').mockReturnValue(1_750_000_000_000);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.INTERNAL_API_KEY;
  });

  it('signs the canonical method, path, query and profile without sending the secret', () => {
    const nonce = 'nonce-1234567890abcdef';
    const target = 'http://intelligence:8000/insights/search?z=two&a=hello+world&a=alpha';
    const headers = intelligenceAuthorityHeaders(profileId.toUpperCase(), target, 'post', 'application/json', 1_750_000_000, nonce);
    const payload = [
      'v1', '1750000000', nonce, 'POST', '/insights/search',
      'a=alpha&a=hello%20world&z=two', profileId, 'application/json', createHash('sha256').update('').digest('hex'),
    ].join('\n');

    expect(headers['x-gdpr-internal-key']).toBe(createHmac('sha256', secret).update(payload).digest('hex'));
    expect(headers['x-gdpr-internal-key']).not.toBe(secret);
    expect(headers['x-gdpr-internal-version']).toBe('v1');
    expect(headers['x-gdpr-profile-id']).toBe(profileId);
  });

  it('binds the exact transmitted mutation bytes', () => {
    const args = ['POST','application/json',1_750_000_000,'nonce-body-binding-1234'] as const;
    const first=intelligenceAuthorityHeaders(profileId,'/ingest',...args,'{"value":1}');
    const second=intelligenceAuthorityHeaders(profileId,'/ingest',...args,'{"value":2}');
    expect(first['x-gdpr-internal-key']).not.toBe(second['x-gdpr-internal-key']);
    expect(first['x-gdpr-content-sha256']).toBe(createHash('sha256').update('{"value":1}').digest('hex'));
  });

  it('binds signatures to method, path, query and profile', () => {
    const args = [1_750_000_000, 'nonce-1234567890abcdef'] as const;
    const signature = (profile: string, target: string, method: string) =>
      intelligenceAuthorityHeaders(profile, target, method, 'application/json', ...args)['x-gdpr-internal-key'];
    const baseline = signature(profileId, '/query/tools?a=1', 'GET');

    expect(signature(profileId, '/query/tools?a=1', 'POST')).not.toBe(baseline);
    expect(signature(profileId, '/query/other?a=1', 'GET')).not.toBe(baseline);
    expect(signature(profileId, '/query/tools?a=2', 'GET')).not.toBe(baseline);
    expect(signature('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '/query/tools?a=1', 'GET')).not.toBe(baseline);
  });

  it('fails closed when INTERNAL_API_KEY is absent', () => {
    delete process.env.INTERNAL_API_KEY;
    expect(() => intelligenceAuthorityHeaders(profileId, '/query/tools')).toThrow('INTERNAL_API_KEY is required');
  });

  it('matches the shared cross-runtime canonical URL vectors and rejects malformed escapes', () => {
    const vectors = JSON.parse(readFileSync(resolve(process.cwd(), 'tests/fixtures/r1_internal_authority_vectors.json'), 'utf8')) as Array<{target:string;path:string;query:string}>;
    for (const vector of vectors) expect(canonicalIntelligenceTarget(vector.target)).toEqual({ path: vector.path, query: vector.query });
    expect(() => canonicalIntelligenceTarget('/bad/%ZZ')).toThrow();
  });
});
