import { defineConfig } from '@playwright/test';

const localChromiumExecutable = process.env.R0_CHROMIUM_EXECUTABLE;

export default defineConfig({
  testDir: '../tests/browser',
  globalSetup: process.env.R0_EXECUTE_BROWSER === '1' ? '../tests/browser/r0-global-setup.ts' : undefined,
  outputDir: '../tests/browser/test-results',
  reporter: [['list'], ['junit', { outputFile: '../test-results/playwright-junit.xml' }], ['html', { outputFolder: '../tests/browser/playwright-report', open: 'never' }]],
  timeout: 30_000,
  fullyParallel: false,
  workers: process.env.R0_EXECUTE_BROWSER === '1' ? 1 : undefined,
  use: {
    baseURL: process.env.R0_BASE_URL,
    trace: process.env.R0_EXECUTE_BROWSER === '1' ? 'on' : 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: process.env.R0_EXECUTE_BROWSER === '1' ? 'on' : 'only-on-failure',
  },
  projects: [{
    name: 'chromium',
    use: {
      browserName: 'chromium',
      ...(localChromiumExecutable ? { launchOptions: { executablePath: localChromiumExecutable } } : {}),
    },
  }],
});
