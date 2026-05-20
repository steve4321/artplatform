import { test, expect, Page } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('生成页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/generate');
  });

  test('页面标题显示 Generate', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Generate' })).toBeVisible();
  });

  test('管线类型切换 - 场景/角色/2D', async ({ page }) => {
    const sceneBtn = page.getByRole('button', { name: /场景/ });
    const charBtn = page.getByRole('button', { name: /角色/ });
    const art2dBtn = page.getByRole('button', { name: /2D/ });

    await expect(sceneBtn).toBeVisible();
    await expect(charBtn).toBeVisible();
    await expect(art2dBtn).toBeVisible();
  });

  test('Prompt 输入验证 - 少于 10 字符禁用 Generate', async ({ page }) => {
    const generateBtn = page.getByRole('button', { name: 'Generate' });
    await expect(generateBtn).toBeDisabled();
    
    await page.locator('textarea').first().fill('短的');
    await expect(generateBtn).toBeDisabled();
    
    await page.locator('textarea').first().fill('这是一个超过 10 个字符的提示词');
    await expect(generateBtn).toBeEnabled();
  });

  test('Negative Prompt 展开收起', async ({ page }) => {
    const negativeToggle = page.getByText('Negative Prompt');
    
    await negativeToggle.click();
    const negativeInput = page.locator('textarea').nth(1);
    await expect(negativeInput).toBeVisible();
    
    await negativeToggle.click();
    await expect(negativeInput).not.toBeVisible();
  });

  test('质量等级选择', async ({ page }) => {
    const draftBtn = page.getByRole('button', { name: 'Draft' });
    const standardBtn = page.getByRole('button', { name: 'Standard' });
    const highBtn = page.getByRole('button', { name: 'High' });

    await draftBtn.click();
    await expect(draftBtn).toHaveClass(/bg-blue-600/);
    
    await standardBtn.click();
    await expect(standardBtn).toHaveClass(/bg-blue-600/);
    
    await highBtn.click();
    await expect(highBtn).toHaveClass(/bg-blue-600/);
  });

  test('Style 下拉框可选择', async ({ page }) => {
    const styleSelect = page.locator('select').first();
    await expect(styleSelect).toBeVisible();
    
    await styleSelect.selectOption('anime');
    await expect(styleSelect).toHaveValue('anime');
  });

  test('Timeline 区域存在', async ({ page }) => {
    await expect(page.getByText('Timeline')).toBeVisible();
    await expect(page.getByText('Progress')).toBeVisible();
  });

  test('ActionBar 存在但按钮禁用 - 占位符', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'FBX' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'GLB' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Review' })).toBeVisible();
  });
});
