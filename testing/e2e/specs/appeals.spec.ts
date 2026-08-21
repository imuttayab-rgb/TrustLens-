import { expect, test, type Page } from '@playwright/test';

/**
 * The appeal route, end to end, across both apps.
 *
 * This is the journey the FYP is examined on: a seller disagrees with an
 * explainable score and has somewhere to go. It runs against the seeded demo
 * sellers, so it needs `make seed-demo` and both dev servers up.
 */

const WEB = 'http://localhost:3000';
const ADMIN = 'http://localhost:3001';

/**
 * Fill and confirm the value stuck.
 *
 * react-hook-form registers its inputs on hydration, and a fill() that lands
 * first is silently discarded - the form then submits empty and the failure
 * reads as bad credentials rather than a race.
 */
async function signIn(page: Page, email: string, password: string) {
  const emailBox = page.locator('input[type="email"]');
  const passwordBox = page.locator('input[type="password"]');
  await expect(emailBox).toBeVisible({ timeout: 30_000 });
  await page.waitForLoadState('networkidle');

  await expect(async () => {
    await emailBox.fill(email);
    await passwordBox.fill(password);
    await expect(emailBox).toHaveValue(email, { timeout: 2_000 });
    await expect(passwordBox).toHaveValue(password, { timeout: 2_000 });
  }).toPass({ timeout: 60_000 });

  await page.locator('button[type="submit"]').click();
}

test('a seller can dispute a score and a reviewer can resolve it', async ({ browser }) => {
  test.setTimeout(240_000);

  const sellerContext = await browser.newContext();
  const seller = await sellerContext.newPage();
  const sellerErrors: string[] = [];
  seller.on('pageerror', (e) => sellerErrors.push(e.message));

  await seller.goto(`${WEB}/login`, { waitUntil: 'domcontentloaded' });
  await signIn(seller, 'seller.high@trustlens.dev', 'Seller!Passw0rd123');
  await seller.waitForURL('**/dashboard', { timeout: 60_000 });

  await seller.goto(`${WEB}/dashboard/trust-score`, { waitUntil: 'domcontentloaded' });

  const appealButton = seller.getByRole('button', { name: /appeal this score/i });
  await expect(appealButton).toBeVisible({ timeout: 60_000 });
  await appealButton.click();

  const reason = seller.locator('#reason');
  await expect(reason).toBeVisible({ timeout: 20_000 });

  // Below the minimum: the client refuses before a request is sent.
  await reason.fill('nope');
  await seller.getByRole('button', { name: /submit appeal/i }).click();
  await expect(seller.locator('[role="alert"]').first()).toBeVisible({ timeout: 10_000 });

  await seller.locator('#reasonCategory').selectOption('IDENTITY_INCORRECT');
  await reason.fill('The selfie I uploaded clearly matches the photo on my CNIC document.');
  await seller.getByRole('button', { name: /submit appeal/i }).click();

  // The submitted appeal appears in the seller's own thread.
  await expect(seller.getByText(/waiting for a reviewer/i)).toBeVisible({ timeout: 30_000 });
  expect(sellerErrors).toEqual([]);

  // ── Reviewer side ──────────────────────────────────────────────────
  const staffContext = await browser.newContext();
  const staff = await staffContext.newPage();
  const staffErrors: string[] = [];
  staff.on('pageerror', (e) => staffErrors.push(e.message));

  await staff.goto(`${ADMIN}/login`, { waitUntil: 'domcontentloaded' });
  await signIn(staff, 'reviewer@trustlens.dev', 'Review!Passw0rd123');
  // Exact match on the nav link: the dashboard also carries an "Open the
  // review queue" call to action, and a loose regex matches both, which
  // trips Playwright's strict mode before it can assert anything.
  await expect(staff.getByRole('link', { name: 'Review queue', exact: true })).toBeVisible({
    timeout: 60_000,
  });

  await staff.goto(`${ADMIN}/appeals`, { waitUntil: 'domcontentloaded' });

  const row = staff.locator('button:has-text("Identity check")').first();
  await expect(row).toBeVisible({ timeout: 60_000 });
  await row.click();

  const claim = staff.getByRole('button', { name: /claim this appeal/i });
  await expect(claim).toBeVisible({ timeout: 20_000 });
  await claim.click();

  const note = staff.locator('textarea').first();
  await expect(note).toBeVisible({ timeout: 30_000 });

  // The note is what the seller reads, so a decision cannot be recorded
  // without one long enough to be an explanation.
  const record = staff.getByRole('button', { name: /record decision/i });
  await note.fill('too short');
  await expect(record).toBeDisabled();

  await note.fill('Face match re-run against the document photo; the original read was wrong.');
  await expect(record).toBeEnabled();
  await record.click();

  // Resolved appeals leave the work queue.
  await expect(staff.getByText(/no appeals waiting/i)).toBeVisible({ timeout: 30_000 });
  expect(staffErrors).toEqual([]);

  await sellerContext.close();
  await staffContext.close();
});
