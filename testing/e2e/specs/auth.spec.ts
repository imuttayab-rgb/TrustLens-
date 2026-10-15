/** Regression coverage and test support for auth.spec. */
import { expect, test } from '@playwright/test';

test.describe('authentication', () => {
  test('rejects bad credentials without revealing whether the account exists', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email address').fill('nobody@trustlens.dev');
    await page.getByLabel('Password').fill('WrongPassword!123');
    await page.getByRole('button', { name: /sign in/i }).click();

    // Identical message for a wrong password and a missing account.
    //
    // Filtered rather than bare: Next renders an empty `role="alert"` route
    // announcer on every page, so a bare getByRole('alert') matches two
    // elements and trips Playwright's strict mode before it ever reads the
    // message.
    await expect(
      page.getByRole('alert').filter({ hasText: /invalid email or password/i }),
    ).toBeVisible();
  });

  test('signs a seller in and lands on the dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email address').fill('seller.high@trustlens.dev');
    await page.getByLabel('Password').fill('Seller!Passw0rd123');
    await page.getByRole('button', { name: /sign in/i }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  });
});
