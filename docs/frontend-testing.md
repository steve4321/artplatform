# 前端交互自动化测试规范

> 本规范定义了 ArtPlatform 前端交互的自动化测试要求。
> **核心原则**：任何前端改动必须先更新本文档和对应测试，然后才能开始开发。

---

## 测试框架

| 工具 | 用途 | 安装 |
|------|------|------|
| **Playwright** | E2E 浏览器测试 | `npm install -D @playwright/test && npx playwright install --with-deps chromium` |
| **Vitest** | 组件/Store 单元测试 | `npm install -D vitest @vitest/ui` |

---

## 测试文件结构

```
frontend/tests/
├── e2e/
│   ├── auth.spec.ts          # 登录/登出流程
│   ├── dashboard.spec.ts     # 工作台
│   ├── generate.spec.ts      # 生成页面（管线）
│   ├── assets.spec.ts        # 资产管理
│   ├── reviews.spec.ts        # 审批流程
│   └── settings.spec.ts      # 设置页面
├── integration/
│   ├── stores/
│   │   ├── authStore.spec.ts
│   │   ├── assetStore.spec.ts
│   │   └── pipelineStore.spec.ts
│   └── components/
│       ├── AssetCard.spec.tsx
│       ├── AssetGrid.spec.tsx
│       └── AssetFilters.spec.tsx
├── mocks/
│   └── server.ts            # MSW 或内置 mock server
└── helpers/
    ├── login.ts             # 登录辅助函数
    ├── navigation.ts        # 导航辅助函数
    └── waitForPipeline.ts   # 管线状态等待
```

---

## 测试要求矩阵

| 页面 | 必须测试的交互 | 测试类型 |
|------|---------------|----------|
| **LoginPage** | 表单输入、提交、错误显示、登录成功跳转 | E2E |
| **Sidebar** | 各导航链接跳转、高亮状态 | E2E |
| **TopBar** | 下拉菜单开关、登出跳转 | E2E |
| **DashboardPage** | 数据加载、分卡显示 | E2E + Store |
| **GeneratePage** | 管线类型切换、配置输入、Generate 按钮、概念图选择、管线时间线、查看器交互 | E2E |
| **AssetsPage** | 筛选、重置、分页、上传、详情弹窗、下载 | E2E |
| **ReviewsPage** | 审核操作（approve/reject/request changes）、预览弹窗 | E2E |
| **SettingsPage** | 信息显示（无交互） | 快照 |

---

## E2E 测试规范

### 登录流程 (auth.spec.ts)

```typescript
import { test, expect } from '@playwright/test';
import { loginAs, logout } from '../helpers/auth';

test.describe('登录认证', () => {
  test('正确的邮箱密码登录成功并跳转到 dashboard', async ({ page }) => {
    await page.goto('/login');
    
    await page.getByLabel('Email').fill('admin@artplatform.local');
    await page.getByLabel('Password').fill('admin123456');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    // 验证跳转
    await expect(page).toHaveURL('/dashboard');
    // 验证 TopBar 显示
    await expect(page.locator('text=Dashboard')).toBeVisible();
  });

  test('错误密码显示错误提示', async ({ page }) => {
    await page.goto('/login');
    
    await page.getByLabel('Email').fill('admin@artplatform.local');
    await page.getByLabel('Password').fill('wrongpassword');
    await page.getByRole('button', { name: 'Sign In' }).click();
    
    await expect(page.getByText('Login failed')).toBeVisible();
    await expect(page).toHaveURL('/login');
  });

  test('已登录用户访问 /login 重定向到 /dashboard', async ({ page }) => {
    await loginAs(page, 'admin@artplatform.local');
    await page.goto('/login');
    await expect(page).toHaveURL('/dashboard');
  });
});
```

### 生成页面 (generate.spec.ts)

```typescript
import { test, expect } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('生成页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/generate');
  });

  test('管线类型切换 - 场景/角色/2D', async ({ page }) => {
    // 默认场景
    await expect(page.getByRole('button', { name: /场景/ })).toHaveClass(/bg-blue-600/);
    
    // 切换角色
    await page.getByRole('button', { name: /角色/ }).click();
    await expect(page.getByRole('button', { name: /角色/ })).toHaveClass(/bg-blue-600/);
    
    // 切换 2D
    await page.getByRole('button', { name: /2D/ }).click();
    await expect(page.getByRole('button', { name: /2D/ })).toHaveClass(/bg-blue-600/);
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
    
    // 默认收起
    await expect(page.locator('textarea').nth(1)).not.toBeVisible();
    
    // 展开
    await negativeToggle.click();
    await expect(page.locator('textarea').nth(1)).toBeVisible();
    
    // 收起
    await negativeToggle.click();
    await expect(page.locator('textarea').nth(1)).not.toBeVisible();
  });

  test('质量等级选择', async ({ page }) => {
    await page.getByRole('button', { name: 'Draft' }).click();
    await expect(page.getByRole('button', { name: 'Draft' })).toHaveClass(/bg-blue-600/);
    
    await page.getByRole('button', { name: 'Standard' }).click();
    await expect(page.getByRole('button', { name: 'Standard' })).toHaveClass(/bg-blue-600/);
    
    await page.getByRole('button', { name: 'High' }).click();
    await expect(page.getByRole('button', { name: 'High' })).toHaveClass(/bg-blue-600/);
  });

  // ⚠️ 注意：Generate 按钮会启动真实管线，测试时需要 Mock API
  test('Generate 按钮点击调用 API 并显示加载状态', async ({ page }) => {
    // Mock API 响应
    await page.route('**/api/v1/pipelines', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-pipeline-id',
          status: 'pending',
          steps: []
        })
      });
    });

    await page.locator('textarea').first().fill('A medieval warrior with sword and shield');
    await page.getByRole('button', { name: 'Generate' }).click();
    
    // 验证加载状态
    await expect(page.getByText('Generating…')).toBeVisible();
  });
});
```

### 资产页面 (assets.spec.ts)

```typescript
import { test, expect } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('资产页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/assets');
  });

  test('资产筛选 - 类型下拉框', async ({ page }) => {
    await page.locator('select').first().selectOption('model_3d');
    // 验证 API 调用参数
    await expect(page).toHaveURL(/asset_type=model_3d/);
  });

  test('资产筛选 - 状态下拉框', async ({ page }) => {
    await page.locator('select').nth(1).selectOption('review');
    await expect(page).toHaveURL(/state=review/);
  });

  test('搜索框 300ms 防抖', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search"]');
    
    await searchInput.fill('test');
    // 300ms 内不应该触发搜索
    await expect(page).not.toHaveURL(/search=test/);
    
    // 等待防抖
    await page.waitForTimeout(400);
    await expect(page).toHaveURL(/search=test/);
  });

  test('Clear 按钮重置所有筛选', async ({ page }) => {
    await page.locator('select').first().selectOption('model_3d');
    await page.locator('select').nth(1).selectOption('review');
    
    await page.getByRole('button', { name: 'Clear' }).click();
    
    await expect(page).toHaveURL('/assets');
  });

  test('分页 - 下一页', async ({ page }) => {
    const nextBtn = page.getByRole('button', { name: '' }).filter({ has: page.locator('svg') }).last();
    
    // 如果有超过一页的资产
    await nextBtn.click();
    await expect(page).toHaveURL(/page=2/);
  });

  test('点击资产卡片打开详情弹窗', async ({ page }) => {
    // 等待资产加载
    await page.waitForSelector('[class*="AssetCard"]', { timeout: 5000 }).catch(() => {});
    
    const firstCard = page.locator('[class*="cursor-pointer"]').first();
    if (await firstCard.isVisible()) {
      await firstCard.click();
      await expect(page.getByRole('dialog')).toBeVisible();
    }
  });
});
```

### 审批页面 (reviews.spec.ts)

```typescript
import { test, expect } from '@playwright/test';
import { loginAs } from '../helpers/auth';

test.describe('审批页面', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page);
    await page.goto('/reviews');
  });

  test('Approve 操作', async ({ page }) => {
    // 等待待审资产加载
    const approveBtn = page.getByRole('button', { name: 'Approve' }).first();
    
    // Mock confirm 对话框
    page.on('dialog', dialog => dialog.accept());
    
    await approveBtn.click();
    
    // 资产应该从列表移除
    await expect(page.locator('[class*="bg-gray-900"]')).not.toContainText('Approve');
  });

  test('Reject 操作', async ({ page }) => {
    const rejectBtn = page.getByRole('button', { name: 'Reject' }).first();
    
    page.on('dialog', dialog => dialog.accept());
    
    await rejectBtn.click();
    await expect(page.locator('[class*="bg-gray-900"]')).not.toContainText('Reject');
  });

  test('Request Changes 操作', async ({ page }) => {
    const requestChangesBtn = page.getByRole('button', { name: 'Request Changes' }).first();
    
    page.on('dialog', dialog => dialog.accept());
    
    await requestChangesBtn.click();
    await expect(page.locator('[class*="bg-gray-900"]')).not.toContainText('Request Changes');
  });

  test('预览弹窗 - 3D 资产', async ({ page }) => {
    const previewArea = page.locator('[class*="cursor-pointer"]').first();
    
    await previewArea.click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.locator('[class*="AssetViewer"], canvas')).toBeVisible();
    
    // 关闭
    await page.getByText('Close').click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('空状态显示', async ({ page }) => {
    // 当没有待审资产时
    const emptyState = page.getByText('No assets pending review');
    if (await emptyState.isVisible()) {
      await expect(page.getByText('All caught up!')).toBeVisible();
    }
  });
});
```

---

## Store 单元测试规范

### authStore.spec.ts

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAuthStore } from '../../src/stores/authStore';

describe('authStore', () => {
  beforeEach(() => {
    // 重置 store 状态
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null
    });
    localStorage.clear();
  });

  describe('login', () => {
    it('成功登录设置用户状态', async () => {
      // Mock API
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        data: { accessToken: 'test-token' }
      }).mockResolvedValueOnce({
        ok: true,
        data: { id: '1', email: 'test@test.com', displayName: 'Test', role: 'admin' }
      });

      const { result } = renderHook(() => useAuthStore());
      
      await result.current.login('test@test.com', 'password');
      
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.email).toBe('test@test.com');
    });
  });

  describe('logout', () => {
    it('登出清除所有状态', () => {
      useAuthStore.setState({
        user: { id: '1', email: 'test@test.com' },
        token: 'some-token',
        isAuthenticated: true
      });

      const { result } = renderHook(() => useAuthStore());
      result.current.logout();

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBe(null);
      expect(localStorage.getItem('auth_token')).toBe(null);
    });
  });
});
```

---

## 测试辅助函数

### helpers/auth.ts

```typescript
import { Page } from '@playwright/test';

export async function loginAs(page: Page, email: string = 'admin@artplatform.local', password: string = 'admin123456') {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForURL('/dashboard');
}

export async function logout(page: Page) {
  await page.locator('[class*="rounded-full"]').click(); // 用户头像
  await page.getByText('Sign Out').click();
  await page.waitForURL('/login');
}
```

### helpers/navigation.ts

```typescript
import { Page, expect } from '@playwright/test';

export async function navigateTo(page: Page, section: 'dashboard' | 'generate' | 'assets' | 'reviews' | 'settings') {
  const routes = {
    dashboard: '/dashboard',
    generate: '/generate',
    assets: '/assets',
    reviews: '/reviews',
    settings: '/settings'
  };
  
  await page.goto(routes[section]);
  await expect(page).toHaveURL(routes[section]);
}
```

### helpers/waitForPipeline.ts

```typescript
import { Page } from '@playwright/test';

export async function waitForPipelineStatus(
  page: Page,
  status: 'running' | 'completed' | 'failed' | 'paused',
  timeout: number = 60000
) {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeout) {
    const statusBanner = page.locator('[class*="StatusBanner"]');
    if (await statusBanner.isVisible()) {
      const text = await statusBanner.textContent();
      if (status === 'completed' && text?.includes('Pipeline completed')) return;
      if (status === 'failed' && text?.includes('Pipeline failed')) return;
      if (status === 'paused' && text?.includes('concept image')) return;
      if (status === 'running' && text?.includes('Processing')) return;
    }
    await page.waitForTimeout(1000);
  }
  
  throw new Error(`Timeout waiting for pipeline status: ${status}`);
}
```

---

## Mock Server 配置

### mocks/server.ts

```typescript
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

export const server = setupServer(
  // 登录
  http.post('/api/v1/auth/login', () => {
    return HttpResponse.json({ accessToken: 'mock-token' });
  }),
  
  // 获取用户
  http.get('/api/v1/auth/me', () => {
    return HttpResponse.json({
      id: '1',
      email: 'admin@artplatform.local',
      displayName: 'Admin',
      role: 'admin'
    });
  }),
  
  // 资产列表
  http.get('/api/v1/assets', () => {
    return HttpResponse.json({
      items: [],
      total: 0,
      page: 1,
      pageSize: 20
    });
  }),
  
  // 管线
  http.post('/api/v1/pipelines', () => {
    return HttpResponse.json({
      id: 'pipeline-1',
      status: 'pending',
      steps: []
    });
  }),
  
  http.get('/api/v1/pipelines/:id', () => {
    return HttpResponse.json({
      id: 'pipeline-1',
      status: 'running',
      steps: []
    });
  }),
  
  // 更多端点...
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

---

## CI/CD 集成

### GitHub Actions Workflow

```yaml
# .github/workflows/frontend-tests.yml
name: Frontend Tests

on:
  push:
    paths:
      - 'frontend/**'
      - 'docs/frontend-interactions.md'
  pull_request:
    paths:
      - 'frontend/**'
      - 'docs/frontend-interactions.md'

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install dependencies
        working-directory: frontend
        run: npm ci
      
      - name: Install Playwright
        run: npx playwright install --with-deps chromium
      
      - name: Run E2E tests
        working-directory: frontend
        run: npm run test:e2e
      
      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: frontend/test-results/

  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install dependencies
        working-directory: frontend
        run: npm ci
      
      - name: TypeScript check
        working-directory: frontend
        run: npx tsc --noEmit
      
      - name: ESLint
        working-directory: frontend
        run: npm run lint
```

---

## 开发流程要求

### 变更前必须完成

1. **更新文档** (`docs/frontend-interactions.md`)
   - 添加/修改的交互行为
   - 更新 API 调用列表
   - 标注已知问题变化

2. **编写/更新测试**
   - E2E 测试：`frontend/tests/e2e/`
   - 单元测试：`frontend/tests/integration/`

3. **运行测试确保通过**
   ```bash
   cd frontend
   npm run test        # 运行所有测试
   npm run test:e2e    # 仅 E2E
   npm run test:unit   # 仅单元测试
   ```

### PR 检查清单

- [ ] 文档已更新
- [ ] 测试已添加/更新
- [ ] 所有测试通过 (`npm run test`)
- [ ] TypeScript 检查通过 (`npx tsc --noEmit`)
- [ ] ESLint 检查通过 (`npm run lint`)

---

## 测试数据

### 测试用户

| 邮箱 | 密码 | 角色 |
|------|------|------|
| admin@artplatform.local | admin123456 | admin |
| artist@artplatform.local | artist123456 | artist |
| reviewer@artplatform.local | reviewer123456 | reviewer |

### 测试资产

测试时应使用 Mock 数据，避免依赖真实 API。
