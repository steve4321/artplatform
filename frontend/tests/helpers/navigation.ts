import { Page, expect } from '@playwright/test';

const routes: Record<string, string> = {
  dashboard: '/dashboard',
  generate: '/generate',
  assets: '/assets',
  reviews: '/reviews',
  settings: '/settings',
};

/**
 * Navigate to a specific page section
 */
export async function navigateTo(
  page: Page,
  section: 'dashboard' | 'generate' | 'assets' | 'reviews' | 'settings'
): Promise<void> {
  const route = routes[section];
  await page.goto(route);
  await expect(page).toHaveURL(new RegExp(route));
}
