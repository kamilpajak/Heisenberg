import { test, expect } from '@playwright/test';

/**
 * Timeout Flaky Tests
 *
 * These tests demonstrate timeout-related failures that Heisenberg should diagnose.
 * Expected root cause: Timing issues, element appears after timeout.
 */

test.describe('Timeout Flaky Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should wait for slow action to complete', async ({ page }) => {
    // This test is flaky because the action takes 0-6 seconds
    // but the test timeout is 5 seconds
    await page.getByTestId('slow-button').click();

    // Wait for result - this will timeout if delay > 5s
    await expect(page.getByTestId('slow-result')).toContainText('Completed', {
      timeout: 5000,
    });
  });

  test('should find delayed element', async ({ page }) => {
    // Trigger element that appears after 1-5 seconds
    await page.getByTestId('delayed-element-trigger').click();

    // This will timeout if delay is close to 5s
    await expect(page.getByTestId('delayed-element')).toBeVisible({
      timeout: 3000, // Intentionally short timeout
    });
  });

  test('should handle multiple delayed operations', async ({ page }) => {
    // Trigger both delayed operations
    await page.getByTestId('slow-button').click();
    await page.getByTestId('delayed-element-trigger').click();

    // Wait for both - high chance of timeout
    await expect(page.getByTestId('slow-result')).toContainText('Completed');
    await expect(page.getByTestId('delayed-element')).toBeVisible();
  });
});
