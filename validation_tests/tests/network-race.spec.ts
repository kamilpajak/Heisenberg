import { test, expect } from '@playwright/test';

/**
 * Network and Race Condition Tests
 *
 * These tests demonstrate network-related failures and race conditions.
 * Expected root cause: API failures, timing dependencies, async operations.
 */

test.describe('Network and Race Condition Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should handle API call success', async ({ page }) => {
    await page.getByTestId('api-call-button').click();

    // This is flaky - 50% chance of failure
    await expect(page.getByTestId('api-result')).toContainText('Success', {
      timeout: 5000,
    });
  });

  test('should not show error on API call', async ({ page }) => {
    await page.getByTestId('api-call-button').click();

    // Wait for result
    await expect(page.getByTestId('api-result')).toBeVisible();

    // This fails 50% of the time when API returns error
    await expect(page.getByTestId('api-result')).not.toContainText('Error');
  });

  test('should complete race condition in order', async ({ page }) => {
    await page.getByTestId('race-condition-button').click();

    // Wait for race to complete
    await expect(page.getByTestId('api-result')).toContainText('completed', {
      timeout: 3000,
    });

    // The race condition means steps may complete in wrong order
    // This test documents the flaky behavior
  });

  test('should make multiple API calls successfully', async ({ page }) => {
    const button = page.getByTestId('api-call-button');
    const result = page.getByTestId('api-result');

    // Make 3 API calls - each has 50% failure rate
    // Probability of all succeeding: 12.5%
    for (let i = 0; i < 3; i++) {
      await button.click();
      await expect(result).toContainText('Success');
    }
  });

  test('should handle concurrent operations', async ({ page }) => {
    // Trigger multiple async operations at once
    await Promise.all([
      page.getByTestId('api-call-button').click(),
      page.getByTestId('slow-button').click(),
      page.getByTestId('race-condition-button').click(),
    ]);

    // All should complete successfully (very flaky)
    await expect(page.getByTestId('api-result')).toContainText('Success');
    await expect(page.getByTestId('slow-result')).toContainText('Completed');
  });
});
