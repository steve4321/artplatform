# ArtPlatform

面向 Unity 3D 游戏开发的美术资源一站式生成管理平台。

输入文字提示词，自动生成生产级 3D 美术资源（建模 + 材质 + 蒙皮 + 动作）和 2D UI 美术资源（图标 / 立绘 / 卡牌 / 背景），全程 Web 操作，Unity 仅作为消费端。

## 功能特性

 - **提示词驱动**：输入文字描述，自动走完 AI 管线（3D 场景 4 阶段/角色 5 阶段，2D 为 3 阶段）
 - **3D 管线**：文生图 → [人工审核概念图] → 3D 建模 → 网格清理 → UV+材质 → 骨骼绑定 →（动画跳过）
 - **3D 场景流程**：文生图 → [人工审核概念图] → 3D 建模 → 网格清理 → UV+材质（4 阶段，无需骨骼/动画）
 - **3D 角色流程**：文生图 → [人工审核概念图] → 3D 建模 → 网格清理 → UV+材质 → 骨骼绑定（5 阶段）
 - **2D 管线**：文生图 → 去背景+后处理 → PNG / Sprite Sheet / 9-Patch 产出
 - **3D Web 预览**：浏览器内实时预览（旋转/缩放/线框/骨骼）
- **2D Web 预览**：透明棋盘格背景、去背景对比、Sprite 帧播放
- **团队协作**：RBAC 权限管理、Review 审批流
- **Unity 就绪**：导出 FBX + 纹理 / PNG 贴图，拖入 Unity 即可使用
- **CLI 工具**：命令行操作，支持脚本自动化和 CI/CD 集成
 - **MCP 服务**：AI 助手可直接调用平台能力（Claude / Cursor / Copilot）
 - **Provider 设置**：3D 场景/3D 角色/2D 各有独立的默认模式和阶段覆盖配置，支持第三方 API 密钥管理，可跳过不需要的阶段

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.11 | 后端运行时 |
| Node.js | >= 18 | 前端构建 |
| npm | >= 9 | 包管理 |

> **本地开发不需要 Docker**。设置 `LOCAL_DEV=true` 后，数据库使用 SQLite，文件存储使用本地磁盘，任务队列使用同步模式，零外部依赖。

### 1. 启动后端

```bash
cd backend

# 安装依赖（推荐使用清华镜像）
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置环境变量
cp .env.example .env
# 编辑 .env，设置 LOCAL_DEV=true

# 初始化数据库
LOCAL_DEV=true alembic upgrade head

# 启动服务
LOCAL_DEV=true uvicorn app.main:app --reload --port 8000
```

默认管理员账号：`admin@artplatform.local` / `admin123456`

### 2. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（自动代理 /api → localhost:8000）
npm run dev
```

打开 http://localhost:5173 ，使用默认账号登录。

### 3. 使用流程

1. **登录**：输入邮箱密码，进入 Dashboard
2. **生成资源**：点击 Generate → 输入提示词 → 点 Generate → 等待管线执行
3. **浏览资产**：Assets 页面查看所有生成的资源，支持搜索和筛选
4. **审批**：Reviews 页面审批待审资产（Approve / Reject / Request Changes）
5. **下载**：在资产详情页下载 FBX / GLB / Unity 包

### 4. CLI 使用

```bash
# 安装后端后，artplatform 命令自动可用

# 登录
artplatform login --email admin@artplatform.local

# 查看当前用户
artplatform whoami

# 列出资产
artplatform assets list
artplatform assets list --state processing --type model_3d

# 创建资产并上传文件
artplatform assets create --name "Sword" --type model_3d
artplatform assets upload <id> ./model.glb

# 下载资产
artplatform assets download <id> --version 1 -o ./output/

# 运行管线
artplatform pipeline run --prompt "a fantasy warrior character"
artplatform pipeline status <pipeline-id> --watch

# 提交审批
artplatform reviews submit <asset-id> --version 1 --decision approved --notes "Looks good"
```

### 5. MCP 服务（AI 助手集成）

```bash
# 安装 MCP 依赖
pip install -e ".[mcp]"
```

**Claude Desktop 配置**（`claude_desktop_config.json`）：
```json
{
  "mcpServers": {
    "artplatform": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "cwd": "/path/to/artplatform/backend"
    }
  }
}
```

**Cursor 配置**（`.cursor/mcp.json`）：
```json
{
  "mcpServers": {
    "artplatform": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "cwd": "/path/to/artplatform/backend"
    }
  }
}
```

MCP 提供 9 个工具：`generate_3d_asset`、`list_assets`、`get_asset`、`update_asset`、`upload_asset_version`、`export_asset`、`submit_review`、`run_pipeline`、`get_pipeline_status`。

### 6. 本地 AI 模型依赖（可选）

接入真实 AI 模型时，需要克隆推理仓库到 `backend/.local_libs/`：

```bash
cd backend/.local_libs

# TripoSR — 图生 3D 模型
git clone https://github.com/VAST-AI-Research/TripoSR.git

# OpenLRM — 图生 3D 备选模型
git clone https://github.com/3DTopia/OpenLRM.git
```

> `LOCAL_DEV=true` 模式下全部使用 Mock 处理器，不需要这些依赖。仅在使用真实 GPU 推理时需要。

## 部署方案

### 方案一：本地开发模式（当前支持）

适用于开发测试，无需 GPU。

```
LOCAL_DEV=true → SQLite + 本地存储 + Celery 同步执行 + Mock 处理器
```

所有 AI 处理器使用 Mock 实现（生成假的 PNG/GLB 文件），验证完整管线逻辑但不产生真实 AI 输出。

### 方案二：单机 GPU 部署（推荐起步）

一台 GPU 服务器运行全部服务，适合小团队。

```bash
# docker-compose.yml（规划中）
docker-compose up -d
```

**最低配置：**

| 组件 | 要求 |
|------|------|
| GPU | NVIDIA 1× RTX 3090 (24GB) 或 1× A10G (24GB) |
| CPU | 8 核+ |
| 内存 | 32 GB+ |
| 磁盘 | 100 GB SSD（模型 + 生成数据） |

**限制**：HY-Motion 需要 24GB VRAM，与 SDXL/TripoSR 无法同时驻留显存，需要时分复用（先加载 SDXL 生成图片 → 卸载 → 加载 TripoSR 生成 3D → 卸载 → ... → 加载 HY-Motion 生成动画）。

### 方案三：双 GPU 生产部署

适合中大型团队，GPU 工作分离，可并行处理。

| 组件 | 要求 |
|------|------|
| GPU 0 | 1× RTX 4090 (24GB) 或 A100 (40GB) — SDXL + TripoSR |
| GPU 1 | 1× A100 (40GB+) — HY-Motion 专用 |
| CPU | 16 核+ |
| 内存 | 64 GB+ |
| 磁盘 | 500 GB SSD |

**架构**：
```
GPU 0 (24GB): SDXL (~8GB) + TripoSR (~6GB) → 轮流加载，可同时驻留
GPU 1 (40GB): HY-Motion (~24GB) → 常驻，专用
CPU Workers:  Instant Meshes + xatlas + Blender(subprocess) + Rigify
```

### 方案四：Kubernetes 集群（大规模）

适合企业级部署，GPU Worker Pool 自动扩缩容。架构设计已完成，详见 `docs/architecture.md`。

## AI 管线与硬件需求

### 管线流程

#### 3D 管线

**场景流程（4 阶段）** — 用于环境、道具等不需要骨骼动画的对象：
```
Stage 1: 文生图          → 2-4 张概念图 (PNG)
Stage 2: 图生 3D         → 粗糙 3D 网格 (GLB)
Stage 3: 网格清理         → 干净的拓扑网格 (GLB)
Stage 4: UV + 材质烘焙    → 带 PBR 纹理的网格 (GLB + PNG)
```

**角色流程（5 阶段）** — 用于角色，含骨骼绑定（动画阶段已跳过）：
```
Stage 1: 文生图          → 2-4 张概念图 (PNG)
         ↓ [人工审核概念图 — 选择最佳图像继续]
Stage 2: 图生 3D         → 粗糙 3D 网格 (GLB)
Stage 3: 网格清理         → 干净的拓扑网格 (GLB)
Stage 4: UV + 材质烘焙    → 带 PBR 纹理的网格 (GLB + PNG)
Stage 5: 骨骼绑定         → 带骨骼的蒙皮网格 (GLB)
```

> 动画生成阶段（HY-Motion）已跳过，需要 24GB VRAM，当前硬件不支持。

**人工审核点**：3D 建模前，生成的概念图需要人工确认。审核通过后，管线自动继续；审核不通过可重新生成概念图。

#### 2D 管线（3 阶段）

```
"一把燃烧的传奇长剑图标，暗黑风格" (文字提示词)
    │
    ▼
Stage 1: 文生图          → 2-4 张候选图 (PNG)
Stage 2: 后处理           → 去背景 + 统一尺寸 + 可选超分辨率
Stage 3: 格式产出         → PNG / Sprite Sheet / 9-Patch
    │
    ▼
Web 2D 预览 → Review → 发布 → Unity 导入
```

**2D 管线参数：**

| 参数 | 选项 | 默认 |
|------|------|------|
| 用途类型 | icon / portrait / card / background / sprite | icon |
| 输出尺寸 | 64-1024px 或自定义 | 512×512 |
| 去背景 | 是 / 否 | icon/card 默认是 |
| 超分辨率 | 1x / 2x / 4x (Real-ESRGAN) | 1x |

### 各阶段工具与硬件需求

| 阶段 | 工具 | 类型 | VRAM | RAM | 模型大小 | 耗时参考 |
|------|------|------|------|-----|---------|---------|
| 1. 文生图 | **SDXL** | GPU | 8 GB (优化) / 22 GB (标准) | 16 GB+ | 6.94 GB (base) | 2-8s (A100-RTX4090) |
| 1. 文生图 | *SD3 Medium (备选)* | GPU | 12 GB | 16 GB+ | ~5 GB | 3-10s |
| 2. 图生 3D | **TripoSR** | GPU | 6 GB | 8 GB+ | 1.68 GB | <0.5s (A100) |
| 2. 图生 3D | *Stable Fast 3D (备选)* | GPU | 6 GB | 8 GB+ | ~2 GB | <0.5s |
| 3. 网格清理 | **Instant Meshes** | CPU | — | 4 GB+ | 二进制 (50MB) | <1s (<100K 面) |
| 4. UV + 材质 | **xatlas** + **Blender (subprocess)** | CPU | — | 8 GB+ | Blender ~300MB | 10-30s |
| 5. 骨骼绑定 | **Rigify** (via Blender subprocess) | CPU | — | 8 GB+ | 内置于 Blender | 5-15s |
| 6. 动画生成 | **HY-Motion 1.0 Lite** | GPU | **24 GB** | 16 GB+ | ~4 GB (0.46B params) | 10-30s |
| 6. 动画生成 | *Mixamo 预设 (备选)* | — | — | — | Web API | 即时 |
| 2D-2. 去背景 | **rembg** | CPU/GPU | 可选 | 4 GB+ | ~180 MB | <1s |
| 2D-2. 超分辨率 | **Real-ESRGAN** | CPU/GPU | 可选 | 4 GB+ | ~17 MB | 1-3s |

### GPU 选型建议

| GPU | VRAM | 可运行阶段 | 适用场景 |
|-----|------|-----------|---------|
| RTX 3060 | 12 GB | Stage 1 (优化) + Stage 2 | 最低入门，需时分复用 |
| RTX 3090 | 24 GB | Stage 1 + Stage 2 + Stage 6 | **单机推荐**，全部阶段可运行 |
| RTX 4090 | 24 GB | Stage 1 + Stage 2 + Stage 6 | 单机首选，速度最快 |
| A100 40GB | 40 GB | 全部，SDXL+TripoSR 可同时驻留 | 服务器推荐 |
| A100 80GB | 80 GB | 全部，所有模型可同时驻留 | 旗舰配置 |
| 2× A10G | 48 GB | 分卡：GPU0=SDXL+TripoSR, GPU1=HY-Motion | AWS 推荐 |

### 显存时分复用策略（单 GPU）

在单张 24GB GPU 上，通过时分复用运行全部阶段：

```
1. 加载 SDXL (~8GB) → 生成图片 → 卸载       (~8s)
2. 加载 TripoSR (~6GB) → 生成 3D → 卸载     (~1s)
3. [CPU] Instant Meshes 网格清理              (~1s)
4. [CPU] xatlas + Blender UV/材质烘焙         (~30s)
5. [CPU] Rigify 骨骼绑定                      (~15s)
6. 加载 HY-Motion (~24GB) → 生成动画 → 卸载   (~20s)
                                        总计：~75s
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | React + TypeScript + Tailwind | SPA，暗色主题 |
| 3D 预览 | React Three Fiber + drei | 浏览器内 3D 渲染 |
| 后端 | Python FastAPI | 异步 REST API |
| CLI | typer + rich + httpx | 类型安全的命令行工具 |
| MCP | mcp SDK (Python) | AI 助手集成 |
| 数据库 | PostgreSQL / SQLite (dev) | 关系型 + JSONB 元数据 |
| 对象存储 | MinIO / S3 / Local (dev) | 二进制文件存储 |
| 任务队列 | Celery + Redis / Eager (dev) | GPU/CPU Worker 调度 |
| AI 推理 | diffusers + 自定义 Worker | Python 原生，Docker GPU 直通 |
| 3D 处理 | Blender (subprocess) + xatlas + Instant Meshes | 进程隔离，线程安全 |
| 2D 处理 | rembg + Real-ESRGAN | 去背景 + 超分辨率 |
| 动画 | HY-Motion 1.0 Lite | 本地部署，Apache 2.0 |

## 项目结构

```
artplatform/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI 路由 (auth, assets, pipelines, reviews, teams, settings)
│   │   ├── core/           # 配置、数据库、存储、认证
│   │   ├── models/         # SQLAlchemy ORM 模型 (含 provider_setting)
│   │   ├── schemas/        # Pydantic 请求/响应模式
│   │   ├── pipeline/       # 管线编排、处理器注册、Celery Runner、STAGE_DEFINITIONS
│   │   ├── workers/        # 阶段处理器 (mock / local / cloud)
│   │   ├── services/       # 业务逻辑 (导出服务等)
│   │   ├── cli/            # typer CLI 命令
│   │   └── mcp/            # MCP Server
│   ├── tests/              # pytest 测试
│   ├── alembic/            # 数据库迁移
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/            # axios 客户端 (snake_case→camelCase 自动转换)
│   │   ├── stores/         # zustand 状态管理 (auth, asset, pipeline, review, dashboard, providerSettings)
│   │   ├── pages/          # 页面组件 (Login, Dashboard, Generate, Assets, Reviews, Settings)
│   │   ├── components/     # 3D 预览器、布局、资产卡片
│   │   └── types/          # TypeScript 类型定义
│   └── package.json
└── docs/
    └── architecture.md     # 完整架构设计文档
```

## 测试

```bash
cd backend
LOCAL_DEV=true python -m pytest tests/ -v
```

测试覆盖：认证 (6)、资产 CRUD (11)、管线 (6)、审批 (5)、团队 (5)、Provider 设置 (13+)。

## 开发状态

- [x] 后端 API + JWT 认证 + RBAC 权限
- [x] 资产 CRUD + 版本管理 + 状态机
- [x] 3D 管线：场景流程（4 阶段）+ 角色流程（5 阶段）
- [x] 概念图人工审核暂停/继续机制
- [x] UV+材质烘焙（Python 栅格化投影）
- [x] 2D 美术管线（3 阶段：文生图 → 后处理 → 格式产出）
- [x] 前端全页面对接真实 API（登录、Dashboard、Generate、Assets、Reviews、Settings）
- [x] Provider 设置页面（每阶段独立配置 mock/local/cloud + API 密钥管理）
- [x] CLI 工具（9 个命令）
- [x] MCP Server（10 个工具 + 1 个 Prompt 模板）
- [x] 自动化测试（含 Provider 设置测试）
- [ ] 接入真实 AI 模型（需 GPU 环境）
- [ ] Docker Compose 生产部署
- [ ] 3D 预览器对接真实 GLB 文件
- [ ] 2D 预览器（棋盘格背景、去背景对比、Sprite 帧播放）
- [ ] WebSocket 实时推送管线进度 [v2]

## 许可证

MIT
