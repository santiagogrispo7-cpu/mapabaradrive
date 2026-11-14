import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    viewport: { width: 1440, height: 900 },
    browserName: 'chromium',
    channel: 'msedge',
    launchOptions: { args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'] },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    { command: 'npm run dev', url: 'http://127.0.0.1:5173', timeout: 60_000, reuseExistingServer: false },
    { command: 'npm run preview', url: 'http://127.0.0.1:4173', timeout: 60_000, reuseExistingServer: false },
  ],
});
