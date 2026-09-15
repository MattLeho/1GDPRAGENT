// Negative control: test-only source identified by both a `__tests__` directory
// and a `*.test.*` filename, sitting inside an otherwise runtime tree.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

describe('ddl assertions', () => {
  const migration = readFileSync('database/migrations/035_example.sql', 'utf8');

  it('keeps the table and index definitions in migrations', () => {
    expect(migration).toMatch(/ALTER TABLE policy_analyses ALTER COLUMN profile_id SET NOT NULL/i);
    expect(migration).toMatch(/CREATE TABLE IF NOT EXISTS policy_analyses/i);
    expect(migration).toMatch(/CREATE INDEX IF NOT EXISTS policy_analyses_profile_idx/i);
  });
});
