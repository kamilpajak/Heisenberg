import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Heisenberg validation tests.
 *
 * These tests are INTENTIONALLY FLAKY to generate various failure types
 * for validating Heisenberg's root cause analysis capabilities.
 */
export default defineConfig({
  testDir: './tests',

  // Short timeout to trigger timeout failures quickly
  timeout: 5000,

  // No retries - we want to capture failures
  retries: 0,

  // Run tests in parallel
  fullyParallel: true,

  // Fail the build on console errors
  forbidOnly: !!process.env.CI,

  // Reporter configuration
  reporter: [
    ['list'],
    ['json', { outputFile: 'playwright-report.json' }],
  ],

  // Output directory for traces and screenshots
  outputDir: 'test-results',

  // Shared settings for all projects
  use: {
    // Base URL for the test app
    baseURL: 'http://localhost:3333',

    // Collect trace on failure
    trace: 'on-first-retry',

    // Take screenshot on failure
    screenshot: 'only-on-failure',
  },

  // Web server configuration - serves the test app
  webServer: {
    command: 'npx serve test-app -p 3333',
    url: 'http://localhost:3333',
    reuseExistingServer: !process.env.CI,
    timeout: 10000,
  },

  // Projects - just chromium for validation
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
