import { test, expect, Page } from '@playwright/test';

/**
 * Login as a test user
 * @param page Playwright page
 * @param email User email (default: admin test account)
 * @param password User password (default: admin123456)
 */
export async function loginAs(
  page: Page,
  email: string = 'admin@artplatform.local',
  password: string = 'admin123456'
): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

/**
 * Logout current user
 */
export async function logout(page: Page): Promise<void> {
  // Click user avatar to open dropdown
  const avatarButton = page.locator('header button').filter({ has: page.locator('span') }).first();
  await avatarButton.click();
  await page.getByText('Sign Out').click();
  await page.waitForURL('**/login', { timeout: 5000 });
}
