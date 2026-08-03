/**
 * R0 authenticated browser baseline.
 *
 * These specifications intentionally assert the user-visible contract that the
 * July 2026 audit says is broken.  They are regression specifications, not a
 * claim that the checked-out product currently passes them.
 *
 * Required environment:
 *   R0_BASE_URL=http://127.0.0.1:3000
 *   R0_USERNAME=<seeded authenticated profile username>
 *   R0_PASSWORD=<that profile password>
 * Optional:
 *   R0_REQUEST_ID=<an existing request id for request-chat coverage>
 */
import { expect, test, type Page, type TestInfo } from '@playwright/test';

const baseURL = process.env.R0_BASE_URL ?? 'http://127.0.0.1:3000';
const username = () => process.env.R0_USERNAME;
const password = () => process.env.R0_PASSWORD;
const requestId = () => process.env.R0_REQUEST_ID;
const evidenceByPage = new WeakMap<Page, BrowserEvidence>();

type BrowserEvidence = {
  console: Array<{ type: string; text: string }>;
  requests: Array<{ method: string; url: string; status?: number }>;
};

async function capture(page: Page, testInfo: TestInfo, evidence: BrowserEvidence) {
  await page.screenshot({ path: testInfo.outputPath('failure.png'), fullPage: true });
  await testInfo.attach('console-and-network.json', {
    body: Buffer.from(JSON.stringify(evidence, null, 2)),
    contentType: 'application/json',
  });
}

test.beforeEach(async ({ page }, testInfo) => {
  if (!username() || !password()) throw new Error('R0 global setup did not create the disposable authenticated browser profile.');
  const evidence: BrowserEvidence = { console: [], requests: [] };
  page.on('console', message => evidence.console.push({ type: message.type(), text: message.text() }));
  page.on('response', response => {
    if (response.url().includes('/api/')) evidence.requests.push({ method: response.request().method(), url: response.url(), status: response.status() });
  });
  evidenceByPage.set(page, evidence);
  testInfo.annotations.push({ type: 'r0-evidence', description: 'Each failure includes failure.png plus console-and-network.json.' });

  const login = await page.request.post(`${baseURL}/api/auth/login`, {
    data: { username: username()!, password: password()! },
    failOnStatusCode: false,
  });
  expect(login.status(), 'disposable browser profile must authenticate through the canonical login endpoint').toBe(200);
  expect((await login.json()).success).toBe(true);
  await page.goto(`${baseURL}/dashboard/home`);
  await expect(page).toHaveURL(/\/dashboard\/home/);
});

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    await capture(page, testInfo, evidenceByPage.get(page) ?? { console: [], requests: [] });
  }
});

test('R0-AUTH-001: missing, malformed, and stale sessions fail safely', async ({ page }) => {
  const endpoints = ['/api/connectors', '/api/graph'];
  for (const endpoint of endpoints) {
    const missing = await page.request.get(`${baseURL}${endpoint}`, { failOnStatusCode: false, headers: { cookie: '' } });
    expect(missing.status(), `${endpoint} without a session`).toBe(401);
    const malformed = await page.request.get(`${baseURL}${endpoint}`, { failOnStatusCode: false, headers: { cookie: 'gdpr-session=not-a-valid-token' } });
    expect(malformed.status(), `${endpoint} with a malformed session`).toBe(401);
  }

  // A freshly authenticated page must also fail closed after session removal.
  await page.context().clearCookies();
  await page.goto(`${baseURL}/dashboard/graph`);
  await expect(page).toHaveURL(/\/login/);

  // A token-shaped but invalid cookie represents a stale browser shell. The
  // proxy must not treat its mere presence as authenticated authority.
  await page.context().addCookies([{ name: 'gdpr-session', value: 'not-a-valid-token', url: baseURL }]);
  const staleApi = await page.request.get(`${baseURL}/api/graph`, { failOnStatusCode: false, maxRedirects: 0 });
  expect(staleApi.status(), 'a stale cookie must be rejected by canonical API authority').toBe(401);
  await page.goto(`${baseURL}/dashboard/graph`);
  await expect(page).toHaveURL(/\/login/);
});

test('R0-AUTH-002: connector definitions remain selectable for an authenticated profile', async ({ page }) => {
  await page.goto(`${baseURL}/dashboard/settings`);
  await page.getByRole('tab', { name: 'Connectors' }).click();
  const sourceType = page.getByText('Source type').locator('..');
  const connectorSelector = sourceType.getByRole('combobox');
  await expect(connectorSelector, 'authenticated connector UI must expose a usable Source type selector').toBeVisible({ timeout: 5_000 });
  const selectorBox = await connectorSelector.boundingBox();
  expect(selectorBox, 'Source type selector must have an on-screen bounding box').not.toBeNull();
  await connectorSelector.click();
  await expect(page.getByRole('option', { name: 'R0 scoped files' })).toBeVisible();
});

test('R0-AUTH-003: authenticated graph API is not a 401', async ({ page }) => {
  const graph = await page.request.get(`${baseURL}/api/graph?limit=1`, { failOnStatusCode: false });
  expect(graph.status(), 'authenticated graph request must return a usable graph response').toBe(200);
  await expect(graph.json()).resolves.toMatchObject({ dbStatus: 'r0-test-double', nodes: [], links: [] });
  await page.goto(`${baseURL}/dashboard/graph`);
  await expect(page.getByText('Graph API returned 401')).toHaveCount(0);
});

test('R0-PROFILE-001: saving profile refreshes dashboard header identity', async ({ page }) => {
  const updatedName = `R0 Browser ${Date.now()}`;
  try {
    await page.goto(`${baseURL}/dashboard/settings`);
    await page.getByRole('tab', { name: 'Profile & Identity' }).click();
    await page.locator('#username').fill(updatedName);
    await page.getByRole('button', { name: 'Save Profile' }).click();
    await expect(page.getByText('Profile updated successfully')).toBeVisible();
    // The shell is deliberately not reloaded: this detects the reported stale header.
    await expect(page.locator('header').getByText(updatedName, { exact: true })).toBeVisible();
  } finally {
    const restore = await page.request.post(`${baseURL}/api/settings/profile`, { multipart: { username: username()!, email: `${username()}@local` } });
    expect(restore.ok(), 'R0 profile mutation cleanup must succeed even after an assertion failure').toBeTruthy();
  }
});

test('R0-DB-001: requests dashboard has no updated_at database console error', async ({ page }) => {
  const databaseErrors: string[] = [];
  page.on('console', message => {
    if (/updated_at|column .*updated_at|database/i.test(message.text())) databaseErrors.push(message.text());
  });
  await page.goto(`${baseURL}/dashboard/home`);
  await page.waitForLoadState('networkidle');
  expect(databaseErrors).toEqual([]);
  await expect(page.getByText(/updated_at|Database query failed/i)).toHaveCount(0);
});

test('R0-MODEL-001: request chat does not silently default to Google', async ({ page }) => {
  const response = await page.request.post(`${baseURL}/api/request-threads/${requestId()}/chat`, {
    data: { message: 'R0 route-selection probe: do not disclose data.' },
    failOnStatusCode: false,
  });
  expect(response.status(), 'R0 test adapter must exercise the request-chat route without an external provider').toBe(200);
  await expect(response.json()).resolves.toEqual({ success: true, response: 'R0 browser baseline: provider execution disabled.', toolsUsed: [], iterations: 0 });
});

test('R0-UI-001: narrow settings layout has no horizontal overflow or clipped controls', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${baseURL}/dashboard/settings`);
  await page.getByRole('tab', { name: 'Connectors' }).click();
  const dimensions = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }));
  expect(dimensions.scrollWidth, 'settings must fit a 390px viewport').toBeLessThanOrEqual(dimensions.clientWidth);
  const addSource = page.getByRole('button', { name: 'Add source' });
  await expect(addSource).toBeVisible();
  const box = await addSource.boundingBox();
  expect(box, 'Add source must have an on-screen bounding box').not.toBeNull();
  expect(box!.x + box!.width, 'Add source must not be clipped at 390px').toBeLessThanOrEqual(390);
});

test('R0-OPS-001: dashboard does not report a literal always-online status', async ({ page }) => {
  await page.goto(`${baseURL}/dashboard/home`);
  await expect(page.getByText('System Online', { exact: true })).toHaveCount(0);
});
