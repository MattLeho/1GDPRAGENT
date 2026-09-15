// Negative control (positive detection): runtime application code that owns
// schema DDL.  Both R0 runtime-DDL scanners must keep reporting this file.
import { db } from './db';

const schema = `
  ALTER TABLE policy_analyses ADD COLUMN IF NOT EXISTS profile_id UUID;
  CREATE INDEX IF NOT EXISTS policy_analyses_profile_idx ON policy_analyses(profile_id);
`;

export async function ensureSchema(): Promise<void> {
  await db.query(schema);
}
