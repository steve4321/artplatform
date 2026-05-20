import { test, expect } from '@playwright/test';
import { loginAs, logout } from '../helpers/auth';

test.describe('登录认证', () => {
  test('正确的邮箱密码登录成功并跳转到 dashboard', async ({ page }) => {
    await page.goto('/login');
    
    await page.getByLabel('Email').fill('admin@artplatform.local');
    await page.getByLabel('Password').fill('admin123456');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('错误密码显示错误提示', async ({ page }) => {
    await page.goto('/login');
    
    await page.getByLabel('Email').fill('admin@artplatform.local');
    await page.getByLabel('Password').fill('wrongpassword');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    await expect(page.getByText('Login failed')).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test('未登录用户访问 /dashboard 重定向到 /login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
  });

  test('已登录用户访问 /login 重定向到 /dashboard', async ({ page }) => {
    await loginAs(page);
    await page.goto('/login');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('Sign Out 登出并跳转 login', async ({ page }) => {
    await loginAs(page);
    await logout(page);
    await expect(page).toHaveURL(/\/login/);
  });
});
