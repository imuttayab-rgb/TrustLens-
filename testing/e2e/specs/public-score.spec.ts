import { expect, test } from '@playwright/test';

/**
 * The buyer journey: an anonymous visitor checks a seller before paying.
 *
 * These assertions encode product guarantees, not implementation details -
 * the score must be visible without an account, the reasons must be shown,
 * and no PII may leak onto the public page.
 */
test.describe('public seller page', () => {
  test('shows a score and its reasons without signing in', async ({ page }) => {
    await page.goto('/seller/ayesha-traders');

    await expect(page.getByRole('img', { name: /trust score/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'ayesha-traders' })).toBeVisible();
    await expect(page.getByText(/why this score/i)).toBeVisible();
  });

  test('never exposes personal data', async ({ page }) => {
    await page.goto('/seller/ayesha-traders');
    const body = (await page.textContent('body')) ?? '';

    // The public schema has no field for any of these. If one appears, a
    // serialiser somewhere started leaking - fail loudly.
    expect(body).not.toMatch(/\d{5}-\d{7}-\d/); // CNIC
    expect(body).not.toMatch(/\+\d{10,15}/); // phone
    expect(body).not.toMatch(/[\w.+-]+@[\w-]+\.[\w.]+/); // email
  });

  test('a high-risk seller is not rendered as reassuring', async ({ page }) => {
    await page.goto('/seller/quick-deals-pk');
    await expect(page.getByText(/high risk/i)).toBeVisible();
  });
});
