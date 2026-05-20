import { test, expect } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('工作台页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/dashboard');
  });

  test('页面标题显示 Dashboard', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('显示统计卡片', async ({ page }) => {
    await expect(page.getByText('Total Assets')).toBeVisible();
    await expect(page.getByText('Pending Reviews')).toBeVisible();
    await expect(page.getByText('Active Pipelines')).toBeVisible();
  });

  test('Recent Assets 列表区域存在', async ({ page }) => {
    await expect(page.getByText('Recent Assets')).toBeVisible();
  });
});
