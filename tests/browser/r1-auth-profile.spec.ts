/**
 * R1 browser acceptance against a disposable, hermetic application stack.
 *
 * This file never provisions or mutates a non-disposable account. It skips unless
 * the caller explicitly certifies the stack and supplies disposable credentials:
 *   R1_HERMETIC_BROWSER=1
 *   R0_BASE_URL=http://127.0.0.1:3000 (used by the shared Playwright config)
 *   R1_USERNAME=<disposable account>
 *   R1_PASSWORD=<disposable password>
 */
import { expect, test, type Page } from '../../frontend/node_modules/@playwright/test';

const baseURL = process.env.R0_BASE_URL ?? 'http://127.0.0.1:3000';
const username = process.env.R1_USERNAME;
const password = process.env.R1_PASSWORD;
const hermetic = process.env.R1_HERMETIC_BROWSER === '1' && Boolean(username && password && process.env.R0_BASE_URL);

async function login(page: Page) {
  const response = await page.request.post(`${baseURL}/api/auth/login`, {
    headers: { origin: baseURL, 'x-gdpr-csrf': '1' },
    data: { username, password }, failOnStatusCode: false,
  });
  expect(response.status()).toBe(200);
  await page.goto(`${baseURL}/dashboard/settings`);
  await expect(page).toHaveURL(/\/dashboard\/settings/);
}

test.beforeEach(async ({ page }) => {
  test.skip(!hermetic, 'Requires an explicitly certified hermetic R1 stack and disposable R1 credentials.');
  await login(page);
});

test('a session rejected during an active shell clears it and stops protected calls', async ({ page }) => {
  await page.context().clearCookies();
  await page.context().addCookies([{ name: 'gdpr-session', value: 'v1.malformed.tampered', url: baseURL }]);
  let protectedCalls = 0;
  page.on('request', request => {
    if (/\/api\/(settings|connectors|graph|insights)/.test(request.url())) protectedCalls += 1;
  });
  // Trigger a central protectedFetch from the already-mounted shell after the
  // cookie is replaced; proxy navigation is deliberately not involved.
  await page.getByRole('tab', { name: 'Connectors' }).click();
  await expect(page).toHaveURL(/\/login\?reason=/);
  expect(protectedCalls).toBeGreaterThan(0);
  await expect(page.getByText(/Personal Insights|Knowledge Graph|Settings/)).toHaveCount(0);
  const callsAtRedirect = protectedCalls;
  await page.waitForTimeout(500);
  expect(protectedCalls).toBe(callsAtRedirect);
});

test('connector and graph authorization errors remain authorization errors', async ({ page }) => {
  await page.route('**/api/connectors**', route => route.fulfill({
    status: 403, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'CONNECTOR_AUTHORITY_REJECTED', message: 'Connector authorization failed' } }),
  }));
  await page.goto(`${baseURL}/dashboard/settings`);
  await page.getByRole('tab', { name: 'Connectors' }).click();
  await expect(page.getByText('Connector authorization failed')).toBeVisible();
  await expect(page.getByText(/no connectors|empty selector/i)).toHaveCount(0);

  await page.route('**/api/graph**', route => route.fulfill({
    status: 403, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'GRAPH_AUTHORITY_REJECTED', message: 'Graph authorization failed' } }),
  }));
  await page.goto(`${baseURL}/dashboard/graph`);
  await expect(page.getByText(/Neo4j.*(offline|unavailable|failed)/i)).toHaveCount(0);
});

test('profile edit updates the persistent header without reload', async ({ page }) => {
  const replacement = `R1 Disposable ${Date.now()}`;
  const original = username!;
  try {
    await page.getByRole('tab', { name: 'Profile & Identity' }).click();
    await page.locator('#username').fill(replacement);
    await page.getByRole('button', { name: 'Save Profile' }).click();
    await expect(page.getByText('Profile updated successfully')).toBeVisible();
    await expect(page.locator('header').getByText(replacement, { exact: true })).toBeVisible();
  } finally {
    const restore = await page.request.put(`${baseURL}/api/settings/profile`, {
      headers: { origin: baseURL, 'x-gdpr-csrf': '1' },
      multipart: { username: original, email: `${original}@local` }, failOnStatusCode: false,
    });
    expect(restore.ok(), 'disposable profile cleanup must succeed').toBeTruthy();
  }
});

test('UI logout clears the cookie and protected state cannot be rendered again', async ({ page }) => {
  await expect(page.locator('header')).toBeVisible();
  await page.evaluate(() => {
    sessionStorage.setItem('r1-protected-state-clears', '0');
    window.addEventListener('gdpr:protected-state-cleared', () => {
      const count = Number(sessionStorage.getItem('r1-protected-state-clears') ?? '0');
      sessionStorage.setItem('r1-protected-state-clears', String(count + 1));
    });
  });
  await page.getByRole('button', { name: 'Sign out', exact: true }).first().click();
  await expect(page).toHaveURL(/\/login\?reason=logged_out/);
  expect(await page.evaluate(() => sessionStorage.getItem('r1-protected-state-clears'))).toBe('1');
  expect((await page.context().cookies()).find(cookie => cookie.name === 'gdpr-session')).toBeUndefined();
  const protectedResponse = await page.request.get(`${baseURL}/api/settings/profile`, { failOnStatusCode: false });
  expect(protectedResponse.status()).toBe(401);
  await page.goto(`${baseURL}/dashboard/settings`);
  await expect(page).toHaveURL(/\/login\?reason=/);
  await expect(page.locator('header')).toHaveCount(0);
});
