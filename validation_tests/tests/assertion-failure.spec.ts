import { test, expect } from '@playwright/test';

/**
 * Assertion Failure Tests
 *
 * These tests demonstrate assertion failures due to unexpected values.
 * Expected root cause: Off-by-one bugs, race conditions, incorrect expectations.
 */

test.describe('Assertion Failure Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should increment counter correctly', async ({ page }) => {
    const input = page.getByTestId('counter-input');
    const incrementBtn = page.getByTestId('increment-button');

    // Get initial value
    await expect(input).toHaveValue('0');

    // Click increment 3 times
    await incrementBtn.click();
    await incrementBtn.click();
    await incrementBtn.click();

    // Expect value to be 3 (but bug sometimes makes it 4, 5, or 6)
    await expect(input).toHaveValue('3');
  });

  test('should show correct computed value', async ({ page }) => {
    const input = page.getByTestId('counter-input');
    const computed = page.getByTestId('computed-value');
    const incrementBtn = page.getByTestId('increment-button');

    await incrementBtn.click();
    await incrementBtn.click();

    // Get the input value
    const inputValue = await input.inputValue();

    // Computed should match input (but bug sometimes shows wrong value)
    await expect(computed).toContainText(`Computed: ${inputValue}`);
  });

  test('should handle expected vs actual mismatch', async ({ page }) => {
    // Set random value
    await page.getByTestId('random-value-button').click();

    const input = page.getByTestId('counter-input');
    const computed = page.getByTestId('computed-value');

    const inputValue = await input.inputValue();

    // This assertion is flaky due to the display bug
    await expect(computed).toHaveText(`Computed: ${inputValue}`);
  });

  test('should verify static content correctly', async ({ page }) => {
    // This is an intentionally wrong assertion
    await expect(page.getByTestId('app-title')).toHaveText('Wrong Title');
  });

  test('should count elements correctly', async ({ page }) => {
    // Count all buttons in the page
    const buttons = page.locator('button');

    // Intentionally wrong count
    await expect(buttons).toHaveCount(100);
  });
});
