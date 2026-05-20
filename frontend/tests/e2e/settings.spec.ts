import { test, expect } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('设置页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/settings');
  });

  test('页面标题显示 Settings', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  });

  test('Account 区块存在', async ({ page }) => {
    await expect(page.getByText('Account')).toBeVisible();
  });

  test('Email 字段存在', async ({ page }) => {
    await expect(page.getByText('Email')).toBeVisible();
  });

  test('Display Name 字段存在', async ({ page }) => {
    await expect(page.getByText('Display Name')).toBeVisible();
  });

  test('Role 字段存在', async ({ page }) => {
    await expect(page.getByText('Role')).toBeVisible();
  });
});
