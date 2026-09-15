// Negative control: test-only source under a `tests/` directory.  It quotes the
// same DDL literally but executes none of it, so no R0 scanner may report it.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('schema shape', () => {
  const migration = readFileSync('database/migrations/035_example.sql', 'utf8');

  it('adds the ownership column and index', () => {
    expect(migration).toMatch(/ALTER TABLE policy_analyses ADD COLUMN IF NOT EXISTS profile_id UUID/i);
    expect(migration).toMatch(/CREATE INDEX IF NOT EXISTS policy_analyses_profile_idx/i);
    expect(migration).toMatch(/DROP CONSTRAINT IF EXISTS policy_analyses_url_key/i);
  });
});
