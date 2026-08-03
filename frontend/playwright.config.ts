import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../tests/browser',
  globalSetup: process.env.R0_EXECUTE_BROWSER === '1' ? '../tests/browser/r0-global-setup.ts' : undefined,
  outputDir: '../tests/browser/test-results',
  reporter: [['list'], ['junit', { outputFile: '../test-results/playwright-junit.xml' }], ['html', { outputFolder: '../tests/browser/playwright-report', open: 'never' }]],
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: process.env.R0_BASE_URL,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
