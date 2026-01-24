import { test, expect } from '@playwright/test';

/**
 * Selector and DOM Manipulation Tests
 *
 * These tests demonstrate selector failures when DOM changes unexpectedly.
 * Expected root cause: Element removed/replaced, stale element reference.
 */

test.describe('Selector and DOM Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should click button that removes itself', async ({ page }) => {
    const button = page.getByTestId('remove-self-button');

    // First click works
    await button.click();

    // Second click fails - element is gone
    await button.click(); // This will fail with "element not found"
  });

  test('should interact with replaced element', async ({ page }) => {
    const button = page.getByTestId('replace-button');

    // Click to trigger replacement
    await button.click();

    // Try to click original button again - it's been replaced
    await button.click(); // This will fail - original element is gone
  });

  test('should find element with wrong testid', async ({ page }) => {
    // This test has a typo in the testid - will always fail
    await expect(page.getByTestId('non-existent-element')).toBeVisible({
      timeout: 2000,
    });
  });

  test('should handle rapid DOM changes', async ({ page }) => {
    // Get reference to button
    const replaceButton = page.getByTestId('replace-button');

    // Click to trigger replacement
    await replaceButton.click();

    // Immediately try to interact with original - race condition
    await expect(replaceButton).toHaveText('Replace Me');
  });

  test('should verify element after removal', async ({ page }) => {
    const button = page.getByTestId('remove-self-button');

    // Click to remove
    await button.click();

    // Verify button is still there (it's not!)
    await expect(button).toBeVisible();
  });
});
