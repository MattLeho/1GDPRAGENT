import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('policy analysis ownership migration', () => {
    const migration = readFileSync(path.join(process.cwd(), '../database/migrations/035_policy_analysis_request_ownership.sql'), 'utf8');

    it('makes every policy analysis profile- and request-owned without retaining global URL uniqueness', () => {
        expect(migration).toMatch(/ADD COLUMN IF NOT EXISTS profile_id UUID/i);
        expect(migration).toMatch(/ADD COLUMN IF NOT EXISTS request_id UUID/i);
        expect(migration).toMatch(/ALTER TABLE policy_analyses ALTER COLUMN profile_id SET NOT NULL/i);
        expect(migration).toMatch(/ALTER TABLE policy_analyses ALTER COLUMN request_id SET NOT NULL/i);
        expect(migration).toMatch(/DROP CONSTRAINT IF EXISTS policy_analyses_url_key/i);
        expect(migration).toMatch(/ON policy_analyses\(profile_id, request_id, url\)/i);
    });
});
