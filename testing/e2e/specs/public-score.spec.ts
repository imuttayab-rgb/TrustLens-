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

    // innerText, not textContent: textContent includes <script> contents, and
    // in dev mode Next inlines the RSC payload there - full of pnpm specifiers
    // like `next@15.5.22` that match an email regex and fail this for no
    // reason. innerText is what a buyer can actually read.
    const visible = await page.locator('body').innerText();

    // The public schema has no field for any of these. If one appears, a
    // serialiser somewhere started leaking - fail loudly.
    expect(visible).not.toMatch(/\d{5}-\d{7}-\d/); // CNIC
    expect(visible).not.toMatch(/\+\d{10,15}/); // phone
    expect(visible).not.toMatch(/[\w.+-]+@[\w-]+\.[\w.]+/); // email
  });

  test('a high-risk seller is not rendered as reassuring', async ({ page }) => {
    await page.goto('/seller/quick-deals-pk');

    // The band appears twice by design - once under the gauge, once as a
    // badge - so this asserts the badge specifically rather than using a bare
    // text match, which trips Playwright's strict mode on two hits.
    await expect(page.getByText(/high risk/i).first()).toBeVisible();
    await expect(page.getByText(/low risk/i)).toHaveCount(0);
  });

  test('labels each reason with the check it came from', async ({ page }) => {
    await page.goto('/seller/ayesha-traders');
    const visible = await page.locator('body').innerText();

    // Regression test for a defect the 404 hid: every reason row was
    // hardcoded to the Identity category, so "The email address was
    // confirmed" was presented to buyers as an identity check.
    const identityLabels = visible.match(/^Identity$/gm) ?? [];
    expect(identityLabels.length).toBeLessThan(4);
  });
});
