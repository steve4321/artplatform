# 开发规范

## 前端变更流程

> ⚠️ **强制要求**：任何前端代码改动必须遵循以下流程：
> 1. 先更新文档 → 2. 先编写测试 → 3. 然后才能开始开发

### 文档位置
- **前端交互文档**: `docs/frontend-interactions.md`
- **前端测试规范**: `docs/frontend-testing.md`

### 测试要求

| 测试类型 | 框架 | 命令 |
|----------|------|------|
| 单元测试 | Vitest | `npm run test` |
| E2E 测试 | Playwright | `npm run test:e2e` |
| 全部测试 | - | `npm run test:all` |

### 代码检查

```bash
# TypeScript 类型检查
npx tsc --noEmit

# ESLint
npm run lint
```

### PR 前置检查

- [ ] `docs/frontend-interactions.md` 已更新
- [ ] `docs/frontend-testing.md` 已更新
- [ ] 测试已添加/更新
- [ ] `npm run test` 通过
- [ ] `npm run test:e2e` 通过
- [ ] `npx tsc --noEmit` 通过
- [ ] `npm run lint` 通过

---

## 目录结构

```
artplatform/
├── docs/
│   ├── architecture.md        # 架构文档
│   ├── frontend.md           # 前端技术文档
│   ├── frontend-interactions.md  # 前端交互文档（必需维护）
│   └── frontend-testing.md    # 前端测试规范（必需维护）
├── frontend/
│   ├── src/
│   │   ├── api/              # API 客户端
│   │   ├── components/       # React 组件
│   │   ├── pages/           # 页面组件
│   │   ├── stores/          # Zustand 状态
│   │   └── types/           # TypeScript 类型
│   └── tests/
│       ├── e2e/             # Playwright E2E 测试
│       ├── integration/      # 单元/集成测试
│       └── helpers/          # 测试辅助函数
└── backend/
    └── tests/               # pytest 测试
```

---

## 环境要求

### 前端
- Node.js >= 18
- npm >= 9

### 后端
- Python >= 3.11

### 开发模式
```bash
# 后端（SQLite + Mock 处理器）
cd backend
cp .env.example .env
# 编辑 .env 设置 LOCAL_DEV=true
pip install -e ".[dev]"
LOCAL_DEV=true alembic upgrade head
LOCAL_DEV=true uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev  # http://localhost:5173
```

---

## 提交规范

### Commit Message 格式

```
<type>(<scope>): <description>

types: feat, fix, docs, refactor, test, chore
scope: frontend, backend, docs, ci
```

### 示例

```
docs(frontend): update interaction docs for GeneratePage

fix(dashboard): correct API endpoint in fetchDashboard

test(e2e): add reviews page approve workflow tests
```

---

## CI/CD

每次 Push 和 Pull Request 到 main 分支都会自动运行：

### GitHub Actions 工作流

`.github/workflows/frontend.yml` 定义了以下检查：

| 检查 | 描述 | 触发条件 |
|------|------|----------|
| Unit Tests | Vitest 单元测试 | Push/PR (frontend/**) |
| E2E Tests | Playwright E2E 测试 | Push/PR (frontend/**) |
| Test Matrix | 汇总结果 | 所有测试完成后 |

### 本地模拟 CI

```bash
# 运行完整测试套件
npm run test:all

# 快速检查（lint + 类型）
npm run lint
npx tsc --noEmit
```

### 跳过 CI

在提交信息中添加 `[skip ci]` 可以跳过 CI：

```
fix(frontend): quick hotfix [skip ci]
```

---

## 自动化测试覆盖

### 单元测试 (Vitest) - `frontend/tests/integration/`

| 文件 | 测试数量 | 覆盖范围 |
|------|----------|----------|
| authStore.spec.ts | 10 | 登录状态、token 管理 |
| assetStore.spec.ts | 15 | 资产 CRUD、筛选、版本 |
| pipelineStore.spec.ts | 18 | 管线创建、状态、Timeline |

### E2E 测试 (Playwright) - `frontend/tests/e2e/`

| 文件 | 测试数量 | 覆盖范围 |
|------|----------|----------|
| auth.spec.ts | 4 | 登录、登出、重定向 |
| dashboard.spec.ts | 3 | 统计卡片显示 |
| generate.spec.ts | 9 | 管线配置、Prompt 验证、参数 |
| assets.spec.ts | 9 | 资产列表、筛选、上传 |
| reviews.spec.ts | 5 | 审批操作 |
| settings.spec.ts | 5 | 设置页显示 |

**总计**: 43 单元测试 + 35 E2E 测试 = **78 测试**
