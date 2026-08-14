import { request } from '@playwright/test';
import { createRequire } from 'node:module';

// Browser specs live outside the frontend package boundary. Resolve pg from
// that package so Playwright can execute this setup without a duplicate root
// node_modules installation.
const requireFromFrontend = createRequire(`${process.cwd()}/package.json`);
const { Client } = requireFromFrontend('pg') as typeof import('pg');

const baseURL = process.env.R0_BASE_URL ?? 'http://127.0.0.1:3000';
const username = `r0_browser_${Date.now()}`;
const password = 'r0-browser-disposable-password';

export default async function globalSetup() {
  const providerCredentialNames = [
    'GOOGLE_API_KEY', 'GOOGLE_AI_API_KEY', 'GEMINI_API_KEY',
    'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'OPEN_ROUTER_API_KEY',
  ];
  if (providerCredentialNames.some(name => process.env[name])) {
    throw new Error('R0 browser baseline must run without external provider credentials; chat evidence is intentionally limited to the local unconfigured fallback path.');
  }
  if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is required to seed the disposable R0 browser request.');
  const api = await request.newContext({
    baseURL,
    extraHTTPHeaders: { origin: baseURL, 'x-gdpr-csrf': '1' },
  });
  try {
    const registration = await api.post('/api/auth/register', { data: { username, password } });
    if (!registration.ok()) {
      throw new Error(`R0 browser fixture registration failed with ${registration.status()}: ${await registration.text()}`);
    }
  } finally {
    await api.dispose();
  }
  const client = new Client({ connectionString: process.env.DATABASE_URL });
  await client.connect();
  try {
    const result = await client.query<{ id: string; profile_id: string }>(
      `INSERT INTO requests(company_name, status, profile_id)
       SELECT 'R0 browser fixture controller', 'draft', default_profile_id
       FROM user_profiles
       WHERE username = $1
       RETURNING id, profile_id`,
      [username],
    );
    if (result.rowCount !== 1 || !result.rows[0]?.profile_id) {
      throw new Error('R0 browser fixture could not resolve the registered user canonical profile binding.');
    }
    process.env.R0_USERNAME = username;
    process.env.R0_PASSWORD = password;
    process.env.R0_REQUEST_ID = result.rows[0].id;
    process.env.R0_BASE_URL = baseURL;
  } finally {
    await client.end();
  }
}
