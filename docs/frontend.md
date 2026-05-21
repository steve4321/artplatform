# Frontend Documentation

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # Axios 客户端，自动转换 snake_case → camelCase
│   ├── components/
│   │   ├── assets/            # 资产卡片、网格、筛选器、上传对话框
│   │   ├── layout/           # Sidebar（侧边栏）、TopBar（顶部栏）
│   │   └── viewer/           # AssetViewer（3D预览）、AnimationTimeline、WireframeToggle
│   ├── pages/
│   │   ├── LoginPage.tsx     # 登录页
│   │   ├── DashboardPage.tsx  # 仪表盘
│   │   ├── GeneratePage.tsx   # 生成页（核心：管线配置 + 预览）
│   │   ├── AssetsPage.tsx     # 资产管理
│   │   ├── ReviewsPage.tsx    # 审批
│   │   └── SettingsPage.tsx   # 设置
│   ├── stores/               # Zustand 状态管理
│   │   ├── authStore.ts       # 认证状态
│   │   ├── assetStore.ts      # 资产列表
│   │   ├── pipelineStore.ts    # 管线状态（生成进度）
│   │   ├── reviewStore.ts     # 审批状态
│   │   └── dashboardStore.ts  # 仪表盘统计
│   ├── types/
│   │   └── index.ts           # 所有 TypeScript 类型定义
│   ├── App.tsx               # 路由配置
│   └── main.tsx              # 入口
├── vite.config.ts            # Vite 配置（代理 /api → localhost:8000）
└── tailwind.config.js        # Tailwind 暗色主题配置
```

## 技术栈

| 库 | 版本 | 用途 |
|----|------|------|
| React | 18.x | UI 框架 |
| TypeScript | 5.x | 类型安全 |
| Tailwind CSS | 3.x | 样式（暗色主题） |
| Zustand | 4.x | 状态管理 |
| React Router | 6.x | 路由 |
| React Three Fiber | 8.x | 3D 渲染（Three.js） |
| @react-three/drei | 9.x | R3F 辅助组件 |
| axios | 1.x | HTTP 客户端 |

## 启动

```bash
cd frontend
npm install
npm run dev        # 开发服务器 http://localhost:5173
```

开发服务器自动代理 `/api` → `http://localhost:8000`（见 `vite.config.ts`）。

## API 客户端

### 自动转换

`client.ts` 拦截所有请求/响应，自动做 **snake_case → camelCase** 转换：
- 请求： `{ pipeline_type: "3d_scene" }` → `{ pipelineType: "3d_scene" }`
- 响应： `{ pipeline_run_id: "..." }` → `{ pipelineRunId: "..." }`

**注意**：URL 路径参数不转换（如 `/pipelines/{id}` 中的 `id`）

### 认证

Token 存储在 `localStorage['auth_token']`，自动附加到所有请求的 `Authorization: Bearer <token>` 头。401 响应时自动清除 token。

## 状态管理（Zustand）

每个 store 对应一个域，采用相同模式：

```typescript
interface XxxState {
  // 数据
  items: Xxx[];
  isLoading: boolean;
  error: string | null;
  // actions
  fetchXxx: () => Promise<void>;
  createXxx: (data: XxxData) => Promise<void>;
}

export const useXxxStore = create<XxxState>((set, get) => ({
  items: [],
  isLoading: false,
  error: null,
  // ... 实现
}));
```

### 核心 Store

#### `pipelineStore.ts` — 管线状态

**状态**：`currentRun`（当前管线）、`steps`（各阶段状态）、`isLoading`、`error`

**关键方法**：
- `startPipeline(prompt, negativePrompt, stylePreset, quality, pipelineType, config2d?)` — 启动管线
- `pollStatus(pipelineId)` — 轮询状态（每 2 秒）
- `resumePipeline(pipelineId, selectedImageIndex)` — 从暂停点继续（概念图审核后）
- `retryPipeline(pipelineId)` — 重试失败管线
- `deletePipeline(pipelineId)` — 删除管线
- `getCurrentModelUrl()` — 获取当前 GLB URL（从 completed 阶段的 artifact）
- `getCurrentImageUrls()` — 获取当前图片 URL 列表

**管线类型**：`'3d_scene'` | `'3d_character'` | `'2d_art'`

> 注意：`3d_art` 已废弃，统一使用 `3d_character`。

#### `authStore.ts` — 认证

- `login(email, password)` — 登录
- `logout()` — 登出
- `initializeAuth()` — 页面加载时恢复登录状态

#### `assetStore.ts` — 资产

- `fetchAssets(params?)` — 分页获取资产
- `fetchAsset(id)` — 获取单个资产详情

## 页面说明

### GeneratePage（核心页面）

**功能**：配置提示词 → 启动管线 → 预览结果

**Three-way 切换**：场景 / 角色 / 2D

**3D 场景流程**（4 阶段）：
```
文生图 → 3D建模 → 网格清理 → UV+材质
```

**3D 角色流程**（5 阶段）：
```
文生图 → [人工审核] → 3D建模 → 网格清理 → UV+材质 → 骨骼绑定
```

**概念图审核暂停**：
- 3D 管线在 text_to_image 完成后自动暂停
- `currentRun.status === 'paused'` 时，中心预览区显示概念图网格
- 用户选择图像后点"继续生成"调用 `resumePipeline(id, index)`
- StatusBanner 显示黄色暂停状态

**UI 布局**：
```
┌─────────────────────────────────────────────────┐
│  Header: 标题 + 场景/角色/2D 切换器              │
├─────────────────────────────────────────────────┤
│  StatusBanner: 进度条 + 状态标签                │
├────────┬────────────────────────┬──────────────┤
│ Config │  Preview (3D/2D/选择)  │  Timeline    │
│ Panel  │                        │  阶段时间线   │
├────────┴────────────────────────┴──────────────┤
│  ActionBar: 下载FBX/GLB/提交Review            │
└─────────────────────────────────────────────────┘
```

### AssetsPage

资产浏览，支持筛选（类型、状态、标签）。点击资产打开详情 modal，含版本列表和下载按钮。

### ReviewsPage

待审批资产列表，支持 Approve / Reject / Request Changes 操作。

## 类型定义（types/index.ts）

### PipelineType

```typescript
export type PipelineType = '3d_scene' | '3d_character' | '2d_art';
```

### PipelineStatus

```typescript
export type PipelineStatus = 'pending' | 'running' | 'paused' | 'completed' | 'partial' | 'failed';
// 注意：'paused' 是 3D 管线特有的中间状态
```

### StepStatus

```typescript
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
```

### PipelineRun

```typescript
interface PipelineRun {
  id: string;
  assetId: string;
  prompt: string;
  status: PipelineStatus;
  pipelineType: PipelineType;   // 独立字段，不在 config 中
  totalStages: number;
  completedStages: number;
  config: Record<string, unknown>;  // 管线配置参数（不含 pipeline_type）
  steps: PipelineStep[];
}
```

### PipelineStep

```typescript
interface PipelineStep {
  id: string;
  pipelineRunId: string;
  stageOrder: number;
  stage: string;              // 'text_to_image' | 'image_to_3d' | 'cleanup' | ...
  processorName: string;       // 'sdxl' | 'triposr' | ...
  status: StepStatus;
  inputArtifactIds: string[]; // 输入文件 storage_key 列表
  outputArtifactIds: string[];// 输出文件 storage_key 列表
  durationMs: number | null;
  errorMessage: string | null;
}
```

## 3D 预览（AssetViewer）

使用 React Three Fiber + drei：

```tsx
<AssetViewer modelUrl={modelUrl} className="w-full h-full" autoPlay />
```

`modelUrl` 格式：`/local-storage/{storage_key}` — Vite 开发服务器代理到后端静态文件。

支持：旋转、缩放、线框切换、骨骼显示、动画播放（如果有）。

## Tailwind 暗色主题

全局暗色主题，背景 `bg-gray-900` / `bg-gray-800`，文字 `text-gray-100` / `text-gray-400`。

配色：
- Primary: `blue-600`
- Success: `green-600`
- Warning: `yellow-600`
- Danger: `red-600`

## 重要约定

### API 响应转换

后端返回 snake_case，前端自动转 camelCase。**组件内使用 camelCase**。

### Pipeline 暂停状态

**所有 3D 管线**（场景和角色）都会在概念图阶段暂停。`2d_art` 管线不暂停。

暂停发生在 text_to_image 完成后，建模之前。

### Artifact URL

存储路径格式：`pipelines/{pipeline_id}/{stage}/{filename}`

本地存储访问：`/local-storage/{storage_key}`

### Store 轮询

`pipelineStore` 使用 `setInterval` 每 2 秒轮询状态，在 `stopPolling` 时清除。

## 开发注意事项

### Vite 热更新失效

如果热更新不生效，重启 frontend tmux session。

浏览器需要 Ctrl+Shift+R 强制刷新清除缓存。

### TypeScript 检查

```bash
cd frontend && npx tsc --noEmit
```

### 新增页面

1. 在 `pages/` 创建 `XxxPage.tsx`
2. 在 `App.tsx` 添加路由：`<Route path="/xxx" element={<XxxPage />} />`
3. 在 Sidebar 添加导航链接

### 新增 API 端点

1. 后端 API 路径：`/api/v1/xxx`
2. 前端直接用 `client.get('/api/v1/xxx')` 调用（自动附加认证）
3. 如需类型安全，在 `types/index.ts` 添加接口定义

### 新增 Store

1. 在 `stores/` 创建 `xxxStore.ts`
2. 使用 Zustand `create<XxxState>()` 模式
3. 在需要使用的组件中 `import { useXxxStore } from '../stores/xxxStore'`
