# 前端交互文档

> 本文档详细记录 ArtPlatform 前端所有用户交互行为，包括每个点击动作、API 调用和状态变化。
> **维护要求**：任何前端改动必须同步更新本文档和对应的自动化测试。

---

## 路由结构

| URL | 页面组件 | 说明 |
|-----|----------|------|
| `/login` | `LoginPage` | 登录页（未登录用户自动跳转） |
| `/dashboard` | `DashboardPage` | 工作台首页 |
| `/generate` | `GeneratePage` | 资产生成页面 |
| `/assets` | `AssetsPage` | 资产管理页面 |
| `/reviews` | `ReviewsPage` | 审批队列页面 |
| `/settings` | `SettingsPage` | 设置页面 |

---

## 全局布局

```
┌──────────┬────────────────────────────────────────────┐
│          │  TopBar (用户头像 + 通知 + 登出)           │
│ Sidebar  ├────────────────────────────────────────────┤
│ (导航)   │                                            │
│          │              页面内容                       │
│          │                                            │
└──────────┴────────────────────────────────────────────┘
```

---

## 认证流程 (LoginPage)

### 组件文件
`frontend/src/pages/LoginPage.tsx`

### 用户交互

| 点击/输入 | 行为 | 状态变化 | API 调用 |
|-----------|------|----------|----------|
| 输入 Email | 更新 `email` 状态 | - | - |
| 输入 Password | 更新 `password` 状态 | - | - |
| 点击 Sign In | 提交表单 | `isLoading=true`，按钮禁用 | `POST /api/v1/auth/login` |
| 登录成功 | 调用 `login()` | `isAuthenticated=true` | `GET /api/v1/auth/me` 获取用户信息 |
| 登录失败 | 显示红色错误提示 | `error=err.message` | - |
| 表单回车 | 触发 `handleSubmit` | 同点击 Sign In | 同上 |

### 登录成功后的行为
```tsx
await login(email, password);
navigate('/dashboard'); // 跳转到工作台
```

### 错误处理
- API 异常：`setError(errorMessage)`
- 错误显示：红色边框提示框 `{error && <div className="bg-red-500/10...">}`

---

## 侧边栏导航 (Sidebar)

### 组件文件
`frontend/src/components/layout/Sidebar.tsx`

### 导航项

| 导航项 | 目标路径 | 图标 |
|--------|----------|------|
| Dashboard | `/dashboard` | 网格图标 |
| Generate | `/generate` | 闪电图标 |
| Assets | `/assets` | 盒子图标 |
| Reviews | `/reviews` | 审批图标 |
| Settings | `/settings` | 齿轮图标 |

### 用户交互

| 点击 | 行为 |
|------|------|
| 导航链接 | React Router `NavLink` 自动处理：激活状态高亮 + 路由跳转 |

### 激活状态样式
- 激活：`bg-primary-600/10 text-primary-600`
- 非激活：`text-gray-400 hover:bg-gray-800 hover:text-gray-100`

---

## 顶部栏 (TopBar)

### 组件文件
`frontend/src/components/layout/TopBar.tsx`

### 用户交互

| 点击 | 行为 | API 调用 |
|------|------|----------|
| 通知图标 | **占位符**，无功能 | - |
| 用户头像圆形按钮 | 切换下拉菜单 `showDropdown` | - |
| 点击下拉菜单外部 | 关闭下拉菜单（`mousedown` 事件） | - |
| Sign Out | 调用 `logout()` → `navigate('/login')` | - |

### 下拉菜单内容
- 用户名（`user.displayName || user.email`）
- 邮箱（`user.email`）
- Sign Out 按钮

### 状态
```tsx
const [showDropdown, setShowDropdown] = useState(false);
```

---

## 工作台 (DashboardPage)

### 组件文件
`frontend/src/pages/DashboardPage.tsx`

### 页面加载行为

| 时机 | 行为 |
|------|------|
| 组件挂载 (`useEffect`) | 调用 `fetchDashboard()` |

### API 调用（4 个并行请求）

| 请求 | 端点 | 用途 |
|------|------|------|
| 1 | `GET /api/v1/assets?page=1&page_size=1` | `stats.totalAssets` |
| 2 | `GET /api/v1/assets?state=review&page=1&page_size=1` | `stats.pendingReviews` |
| 3 | `GET /api/v1/pipelines?status=running&page=1&page_size=1` | `stats.activePipelines` |
| 4 | `GET /api/v1/assets?page=1&page_size=5` | `recentAssets` |

### 展示内容

| 内容 | 状态字段 |
|------|----------|
| Total Assets | `stats.totalAssets` |
| Pending Reviews | `stats.pendingReviews` |
| Active Pipelines | `stats.activePipelines` |
| Recent Assets 列表 | `recentAssets[]` |

### 状态标签颜色

| 状态 | 颜色 |
|------|------|
| `approved` / `published` | `bg-green-900/50 text-green-400` |
| `review` | `bg-yellow-900/50 text-yellow-400` |
| `processing` | `bg-blue-900/50 text-blue-400` |
| `rejected` / `deprecated` | `bg-red-900/50 text-red-400` |
| 其他 | `bg-gray-800 text-gray-400` |

---

## 生成页面 (GeneratePage) — 最复杂

### 组件文件
`frontend/src/pages/GeneratePage.tsx` (1297 行)

### 布局结构

```
┌────────────────────────────────────────────────────────────────┐
│ Header: 标题 + 管线类型切换器 (场景/角色/2D)                     │
├────────────────────────────────────────────────────────────────┤
│ StatusBanner: 状态标签 + 进度条 + 耗时                          │
├────────────┬───────────────────────────────┬───────────────────┤
│ Config     │  Preview                       │  Timeline         │
│ Panel      │  (3D/2D/概念图选择)            │  阶段时间线       │
│ (配置)     │                               │                   │
├────────────┴───────────────────────────────┴───────────────────┤
│ ActionBar: FBX / GLB / Review (占位符，当前无下载功能)          │
└────────────────────────────────────────────────────────────────┘
```

---

### 资源类型切换 (ResourceTypeSwitcher)

| 点击 | 行为 | 边界条件 |
|------|------|----------|
| 场景 按钮 | 切换为 `3d_scene` | 如果有未完成的管线（pending/running/paused），先 `resetPipeline()` |
| 角色 按钮 | 切换为 `3d_character` | 同上 |
| 2D 按钮 | 切换为 `2d_art` | 同上 |

### 配置面板 - 3D (ConfigPanel3D)

| 点击/输入 | 行为 | 状态字段 |
|-----------|------|----------|
| Prompt 文本框 | 更新提示词 | `prompt` |
| Negative Prompt 箭头 | 展开/收起负面提示词区块 | `showNegative` |
| Negative Prompt 文本框 | 更新负面提示词 | `negativePrompt` |
| Style 下拉框 | 选择风格 | `stylePreset` (realistic/anime/cartoon/fantasy/sci-fi) |
| Draft/Standard/High 按钮 | 选择质量等级 | `quality` |
| Upload 参考图区域 | 打开文件选择器 | `referenceFile` |
| 参考图 X 按钮 | 清除参考图 | `referenceFile = null` |
| Generate 按钮 | 调用 `handleGenerate()` | 禁用条件：`prompt.length < 10` 或 `isBusy` |

### 配置面板 - 2D (ConfigPanel2D)

| 点击/输入 | 行为 | 状态字段 |
|-----------|------|----------|
| Prompt 文本框 | 更新提示词 | `prompt` |
| Negative Prompt 箭头 | 展开/收起 | `showNegative` |
| Style 下拉框 | 选择风格 | `stylePreset` |
| Icon/Portrait/Card/Background/Sprite 按钮 | 选择用途类型 | `usageType` |
| 64/128/256/512/1024 尺寸按钮 | 选择输出尺寸 | `outputSize` |
| Remove/Keep 按钮 | 选择是否去背景 | `removeBackground` |
| PNG/Sprite/9-Patch 按钮 | 选择输出格式 | `outputFormat` |
| Generate 按钮 | 调用 `handleGenerate()` | 同 3D |

### Generate 按钮行为

```tsx
const handleGenerate = useCallback(async () => {
  if (prompt.length < 10 || isBusy) return;
  if (pipelineType === '2d_art') {
    await startPipeline(prompt, negativePrompt, stylePreset, quality, '2d_art', {
      targetSize: outputSize,
      removeBackground,
      outputType: outputFormat,
      usageType,
    });
  } else {
    await startPipeline(prompt, negativePrompt, stylePreset, quality, pipelineType);
  }
}, [...]);
```

**API 调用**: `POST /api/v1/pipelines`

---

### 概念图选择模式（管线暂停状态）

当 `currentRun.status === 'paused'` 且存在概念图时，显示选择界面。

| 点击 | 行为 |
|------|------|
| 概念图卡片 | 选中该图片，设置 `selectedConceptIndex`，显示蓝色边框 |
| Discard & retry 按钮 | 调用 `deletePipeline()` 删除管线，关闭选择界面 |
| Continue to 3D 按钮 | 调用 `resumePipeline(currentRun.id, selectedConceptIndex)` 继续管线 |

### 管线时间线 (PipelineTimeline)

| 点击 | 行为 | 条件 |
|------|------|------|
| 阶段条目（completed/failed 状态） | 调用 `onSelectStage(index)` 选中该阶段 | 仅 `status === 'completed' || status === 'failed'` 时可点击 |
| Retry 按钮 | 调用 `retryPipeline(currentRun.id)` | 存在 failed 阶段时显示 |
| Discard 按钮 | 调用 `deletePipeline(currentRun.id)` | 存在 failed 阶段时显示 |

### 操作栏 (ActionBar) — ⚠️ 占位符

**重要说明**：GeneratePage 底部的 FBX/GLB/Review 按钮是**占位符**，没有任何 `onClick` 处理。

实际下载功能的入口在 **AssetsPage** 的资产详情弹窗中。

| 按钮 | 状态 | 说明 |
|------|------|------|
| FBX | `disabled={!modelUrl \|\| isBusy}` | 无下载功能 |
| GLB | `disabled={!modelUrl \|\| isBusy}` | 无下载功能 |
| Review | `disabled={!modelUrl \|\| isBusy}` | 无提交功能 |

---

### 3D 查看器 (AssetViewer)

### 组件文件
`frontend/src/components/viewer/AssetViewer.tsx`

### 用户交互

| 点击 | 行为 | 技术实现 |
|------|------|----------|
| Wireframe 按钮 | 切换线框模式 | 设置 `wireframe` 状态，遍历所有 mesh 设置 `material.wireframe` |
| Skeleton 按钮 | 切换骨骼辅助线 | 显示/隐藏 `THREE.SkeletonHelper` |
| Auto-Rotate 按钮 | 切换自动旋转 | 设置 `OrbitControls.autoRotate` |
| 鼠标拖拽 | 旋转模型 | `OrbitControls` 处理 |
| 鼠标滚轮 | 缩放 | `OrbitControls` 处理 |

### 动画时间线 (AnimationTimeline)

| 点击 | 行为 |
|------|------|
| 播放/暂停按钮 | 切换 `isPlaying` 状态，调用 `action.play()` 或 `action.stop()` |
| 进度条拖拽 | 更新 `currentTime`，设置 `action.time = time` |

### 状态横幅 (StatusBanner)

| 管线状态 | 显示内容 |
|----------|----------|
| `loading` | "Starting pipeline…" + 加载动画 |
| `running` | "Processing: [阶段名]" + 进度条 + 耗时 |
| `paused` | "Waiting for concept image selection…" + ⏸ 图标 |
| `completed` | "Pipeline completed" + ✓ 图标 |
| `failed` | "Pipeline failed" + ✗ 图标 |

---

## 资产页面 (AssetsPage)

### 组件文件
`frontend/src/pages/AssetsPage.tsx`

### 搜索和筛选 (AssetFilters)

| 点击/输入 | 行为 | API 调用 |
|-----------|------|----------|
| 搜索输入框 | 300ms 防抖后调用 `onSearchChange(localSearch)` | 触发 `setFilters({ search })` → `fetchAssets()` |
| 类型下拉框 | 调用 `onAssetTypeChange(value)` | `setFilters({ assetType })` → `fetchAssets()` |
| 状态下拉框 | 调用 `onStateChange(value)` | `setFilters({ state })` → `fetchAssets()` |
| Clear 按钮 | 调用 `onReset()` → `setLocalSearch('')` | `resetFilters()` → `fetchAssets()` |

### 资产网格 (AssetGrid)

| 点击 | 行为 |
|------|------|
| 资产卡片 | 调用 `onAssetClick(asset)` 打开详情弹窗 |
| 上一页按钮 | 调用 `onPageChange(page - 1)`（页码 > 1 时） |
| 下一页按钮 | 调用 `onPageChange(page + 1)`（页码 < 总页数时） |

### 上传弹窗 (UploadDialog)

| 点击 | 行为 |
|------|------|
| 点击上传区域 | 打开文件选择器 |
| 拖拽文件到区域 | 选中拖拽的文件 |
| Cancel 按钮 | 关闭弹窗，清空选择 |
| Upload 按钮 | 执行上传流程 |

### 上传流程

```tsx
const handleUpload = async () => {
  const asset = await createAsset({ name: uploadName, assetType: uploadType });
  await uploadVersion(asset.id, uploadFile);
  await fetchAssets();
  setUploadDialogOpen(false);
};
```

**API 调用序列**:
1. `POST /api/v1/assets` — 创建资产记录
2. `POST /api/v1/assets/{id}/versions` — 上传文件
3. `GET /api/v1/assets` — 刷新列表

---

### 资产详情弹窗 (AssetDetailModal)

| 点击 | 行为 | API 调用 |
|------|------|----------|
| 遮罩层 | 关闭弹窗 | - |
| X 关闭按钮 | 关闭弹窗 | - |
| Preview 标签 | 切换到预览标签 | `setActiveTab('preview')` |
| Details 标签 | 切换到详情标签 | `setActiveTab('details')` |
| 下载 GLB 按钮 | 直接打开 `/local-storage/{storageKey}` | 无 API 调用 |
| 导出 FBX 按钮 | `GET /api/v1/assets/{id}/export/fbx?version={v}` | 获取下载 URL 并打开 |
| Download (presigned) 按钮 | `GET /api/v1/assets/{id}/versions/{v}/download` | 获取预签名 URL 并打开 |
| Delete 按钮 | 弹出 `window.confirm` → 确认后调用 `deleteAsset()` | `DELETE /api/v1/assets/{id}` |
| Submit for Review 按钮 | 仅 `state === 'draft'` 时显示 | `PATCH /api/v1/assets/{id}/state` |
| 纹理缩略图 | 在新窗口打开大图 | - |

### ⚠️ 已知问题

1. **纹理加载无 loading 状态**：`GET /api/v1/assets/{id}/textures` 请求期间没有任何加载指示器，失败时静默忽略。
2. **下载 GLB 绕过了 API**：直接拼接 `/local-storage/{storageKey}` 路径，与设计文档不一致但实际工作如此。

---

## 审批页面 (ReviewsPage)

### 组件文件
`frontend/src/pages/ReviewsPage.tsx`

### 页面加载

| 时机 | 行为 | API 调用 |
|------|------|----------|
| 组件挂载 | 调用 `fetchReviewQueue()` | `GET /api/v1/assets?state=review&page=1&page_size=50` |

### ⚠️ 审核后不自动刷新

审核操作（Approve/Reject/Request Changes）只从本地列表 `filter` 移除该资产，**不会重新请求 API**。如果审核期间有新的待审资产，用户需要刷新页面才能看到。

| 点击 | 行为 | API 调用 |
|------|------|----------|
| 资产卡片预览区 | 打开预览弹窗 | - |
| Approve 按钮 | `window.confirm` 确认 → `PATCH state=approved` → 本地移除 | `PATCH /api/v1/assets/{id}/state` |
| Reject 按钮 | `window.confirm` 确认 → `PATCH state=rejected` → 本地移除 | `PATCH /api/v1/assets/{id}/state` |
| Request Changes 按钮 | `window.confirm` 确认 → `PATCH state=draft` → 本地移除 | `PATCH /api/v1/assets/{id}/state` |
| 下载 GLB 按钮 | 打开 `/local-storage/{storageKey}` | 无 API |
| 导出 FBX 按钮 | `GET /api/v1/assets/{id}/export/fbx?version={v}` | 获取 URL 并打开 |
| 预览弹窗遮罩 | 关闭预览弹窗 | - |
| Close 按钮 | 关闭预览弹窗 | - |

---

## 设置页面 (SettingsPage)

### 组件文件
`frontend/src/pages/SettingsPage.tsx`

**当前为纯展示页面，无交互功能。**

显示内容：
- Email（只读）
- Display Name（只读）
- Role（只读，badge 显示）
- Team ID（如果有，只读）

---

## API 端点完整列表

| 方法 | 端点 | 调用场景 |
|------|------|---------|
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 获取当前用户 |
| GET | `/api/v1/assets` | 获取资产列表（支持分页、筛选） |
| POST | `/api/v1/assets` | 创建资产 |
| PATCH | `/api/v1/assets/{id}/state` | 更新资产状态 |
| DELETE | `/api/v1/assets/{id}` | 删除资产 |
| GET | `/api/v1/assets/{id}/textures` | 获取纹理列表 |
| GET | `/api/v1/assets/{id}/versions/{v}/download` | 下载资产版本 |
| GET | `/api/v1/assets/{id}/export/fbx` | 导出 FBX |
| POST | `/api/v1/assets/{id}/versions` | 上传资产版本 |
| POST | `/api/v1/pipelines` | 启动管线 |
| GET | `/api/v1/pipelines/{id}` | 获取管线状态 |
| DELETE | `/api/v1/pipelines/{id}` | 删除管线 |
| POST | `/api/v1/pipelines/{id}/retry/{step}` | 重试管线 |
| POST | `/api/v1/pipelines/{id}/resume` | 恢复管线 |
| GET | `/local-storage/{key}` | 访问本地存储文件 |

---

## 状态定义

### 资产状态 (Asset State)

| 状态 | 说明 | 可见性 |
|------|------|--------|
| `draft` | 草稿 | 仅创建者 |
| `processing` | 处理中 | 创建者 |
| `review` | 待审核 | 审核者 |
| `approved` | 已批准 | 所有人 |
| `published` | 已发布 | 所有人 |
| `rejected` | 已拒绝 | 创建者 |
| `deprecated` | 已弃用 | 所有人 |

### 管线状态 (Pipeline Status)

| 状态 | 说明 |
|------|------|
| `pending` | 等待开始 |
| `running` | 运行中 |
| `paused` | 暂停（等待选择概念图） |
| `completed` | 已完成 |
| `failed` | 失败 |
| `partial` | 部分完成 |

---

## 组件清单

### 布局组件

| 组件 | 文件 | 交互 |
|------|------|------|
| Sidebar | `components/layout/Sidebar.tsx` | NavLink 导航 |
| TopBar | `components/layout/TopBar.tsx` | 用户下拉菜单 + 登出 |

### 页面组件

| 组件 | 文件 | 复杂度 |
|------|------|--------|
| LoginPage | `pages/LoginPage.tsx` | 低 |
| DashboardPage | `pages/DashboardPage.tsx` | 低 |
| GeneratePage | `pages/GeneratePage.tsx` | **高**（20+ 交互点） |
| AssetsPage | `pages/AssetsPage.tsx` | 中（16+ 交互点） |
| ReviewsPage | `pages/ReviewsPage.tsx` | 中（11 交互点） |
| SettingsPage | `pages/SettingsPage.tsx` | 无（纯展示） |

### 资产组件

| 组件 | 文件 | 交互 |
|------|------|------|
| AssetCard | `components/assets/AssetCard.tsx` | 点击打开详情 |
| AssetGrid | `components/assets/AssetGrid.tsx` | 分页 |
| AssetFilters | `components/assets/AssetFilters.tsx` | 筛选 + 重置 |
| UploadDialog | `components/assets/UploadDialog.tsx` | 上传 + 拖拽 |

### 查看器组件

| 组件 | 文件 | 交互 |
|------|------|------|
| AssetViewer | `components/viewer/AssetViewer.tsx` | 3D 交互 + 切换 |
| WireframeToggle | `components/viewer/WireframeToggle.tsx` | 切换线框 |
| AnimationTimeline | `components/viewer/AnimationTimeline.tsx` | 播放/暂停 + 拖拽 |
| ModelInfo | `components/viewer/ModelInfo.tsx` | 无（纯展示） |

---

## 已知问题记录

| ID | 位置 | 问题描述 | 严重性 | 状态 |
|----|------|----------|--------|------|
| F001 | GeneratePage ActionBar | FBX/GLB/Review 按钮是占位符，无实际功能 | 中 | 待实现 |
| F002 | ReviewsPage | 审核后不自动刷新队列 | 低 | 设计如此 |
| F003 | AssetDetailModal | 纹理加载无 loading 状态，失败静默忽略 | 低 | 待修复 |
| F004 | TopBar | 移动端汉堡菜单图标无 onClick 处理 | 低 | 废弃 UI |
| F005 | AssetDetailModal | GLB 下载绕过 API 直接访问本地存储 | 低 | 设计不一致 |

---

## 维护日志

| 日期 | 修改内容 | 修改人 |
|------|----------|--------|
| 2026-05-20 | 初始文档创建，涵盖所有交互点和已知问题 | - |
