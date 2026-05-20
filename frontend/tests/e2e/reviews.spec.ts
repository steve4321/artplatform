import { test, expect, Page } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('审批页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/reviews');
  });

  test('页面标题显示 Reviews', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Reviews' })).toBeVisible();
  });

  test('空状态或待审资产列表', async ({ page }) => {
    await page.waitForTimeout(500);
    
    const emptyState = page.getByText('No assets pending review');
    const reviewList = page.locator('[class*="bg-gray-900"]').filter({ has: page.getByRole('button', { name: 'Approve' }) });
    
    const hasEmptyState = await emptyState.isVisible().catch(() => false);
    const hasReviewItems = await reviewList.count();
    
    expect(hasEmptyState || hasReviewItems > 0).toBeTruthy();
  });

  test('Approve 按钮存在则可点击', async ({ page }) => {
    await page.waitForTimeout(500);
    const approveBtn = page.getByRole('button', { name: 'Approve' }).first();
    
    if (await approveBtn.isVisible().catch(() => false)) {
      page.on('dialog', dialog => dialog.accept());
      await approveBtn.click();
    }
  });

  test('Reject 按钮存在则可点击', async ({ page }) => {
    await page.waitForTimeout(500);
    const rejectBtn = page.getByRole('button', { name: 'Reject' }).first();
    
    if (await rejectBtn.isVisible().catch(() => false)) {
      page.on('dialog', dialog => dialog.accept());
      await rejectBtn.click();
    }
  });

  test('Request Changes 按钮存在则可点击', async ({ page }) => {
    await page.waitForTimeout(500);
    const requestBtn = page.getByRole('button', { name: 'Request Changes' }).first();
    
    if (await requestBtn.isVisible().catch(() => false)) {
      page.on('dialog', dialog => dialog.accept());
      await requestBtn.click();
    }
  });

  test('All caught up 提示文字', async ({ page }) => {
    await page.waitForTimeout(500);
    const emptyState = page.getByText('No assets pending review');
    
    if (await emptyState.isVisible()) {
      await expect(page.getByText('All caught up!')).toBeVisible();
    }
  });
});
