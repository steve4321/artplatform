import { test, expect, Page } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('资产页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/assets');
  });

  test('页面标题显示 Assets', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Assets' })).toBeVisible();
  });

  test('搜索框存在', async ({ page }) => {
    await expect(page.locator('input[placeholder*="Search"]')).toBeVisible();
  });

  test('类型筛选下拉框存在', async ({ page }) => {
    const selects = page.locator('select');
    await expect(selects.first()).toBeVisible();
  });

  test('状态下拉框存在', async ({ page }) => {
    const selects = page.locator('select');
    await expect(selects.nth(1)).toBeVisible();
  });

  test('Upload Asset 按钮存在', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Upload Asset' })).toBeVisible();
  });

  test('点击 Upload Asset 打开弹窗', async ({ page }) => {
    await page.getByRole('button', { name: 'Upload Asset' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('Upload Asset')).toBeVisible();
  });

  test('上传弹窗有关闭按钮', async ({ page }) => {
    await page.getByRole('button', { name: 'Upload Asset' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    
    const closeBtn = page.locator('button').filter({ has: page.locator('svg') }).first();
    await closeBtn.click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('资产卡片点击打开详情', async ({ page }) => {
    await page.waitForTimeout(500);
    const cards = page.locator('[class*="cursor-pointer"]');
    const count = await cards.count();
    
    if (count > 0) {
      await cards.first().click();
      await expect(page.getByRole('dialog')).toBeVisible();
    }
  });

  test('空状态显示', async ({ page }) => {
    await page.waitForTimeout(500);
    const emptyState = page.getByText('No assets found');
    if (await emptyState.isVisible()) {
      await expect(page.getByText(/adjust your search or upload/)).toBeVisible();
    }
  });
});
