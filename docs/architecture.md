# ArtPlatform Architecture

美术资源生成与管理平台 — 架构设计文档

## Overview

面向 Unity 3D 游戏开发的美术资源一站式生成管理平台。

- **输入**：文字提示词（可选设计图）
- **输出**：生产级 3D 美术资源（含建模、材质、蒙皮、动作）
- **形态**：Web 平台，Unity 仅作为消费端（效果检查 + 资源导入）

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       Web Frontend (React)                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ 提示词+   │  │ 3D预览器     │  │ 管线时间线│  │ 资产管理    │ │
│  │ 参数面板  │  │ (R3F+Drei)  │  │ 状态展示  │  │ 浏览/搜索   │ │
│  └──────────┘  └──────────────┘  └──────────┘  └─────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│                    API Server (Python FastAPI)                    │
│                 HTTP 轮询 + REST API（WebSocket 为 v2 优化）      │
├──────────┬──────────┬──────────┬──────────┬──────────────────────┤
│  管线编排 │  资产服务 │  团队权限 │  Review  │  导出服务  │  设置服务  │
│  (Celery)│  (CRUD)  │  (RBAC) │  (审批流)│  (Unity/FBX/GLB)│(Provider)│
├──────────┴──────────┴──────────┴──────────┴──────────────────────┤
│               Worker Pool (Docker Compose)                       │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │ GPU Workers │ │ CPU Workers  │ │ Blender Worker (subprocess) │ │
│  │ SDXL+TripoSR│ │ InstantMeshes│ │ Rigify/UniRig + xatlas   │ │
│  │ HY-Motion   │ │ 格式转换     │ │ 材质烘焙                  │ │
│  └─────────────┘ └──────────────┘ └───────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│  MinIO (对象存储)    │    PostgreSQL (元数据)    │    Redis (队列) │
└──────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Design

### 3D Pipeline

**场景流程（4 阶段）** — 用于环境、道具等不需要骨骼动画的对象：

```
Stage 1: 文生图 (SDXL)         → 2-4 张概念图 (PNG)
         ↓ [人工审核 — 概念图暂停点，所有 3D 管线统一暂停]
Stage 2: 图生 3D (TripoSR)    → 粗糙 3D 网格 (GLB)
Stage 3: 网格清理 (Instant Meshes) → 干净的拓扑网格 (GLB)
Stage 4: UV + 材质烘焙        → 带 PBR 纹理的网格 (GLB + PNG)
```

**角色流程（5 阶段）** — 用于角色，含骨骼绑定（动画阶段已跳过）：

```
Stage 1: 文生图 (SDXL)         → 2-4 张概念图 (PNG)
         ↓ [人工审核 — 概念图暂停点]
Stage 2: 图生 3D (TripoSR)    → 粗糙 3D 网格 (GLB)
Stage 3: 网格清理 (Instant Meshes) → 干净的拓扑网格 (GLB)
Stage 4: UV + 材质烘焙        → 带 PBR 纹理的网格 (GLB + PNG)
Stage 5: 骨骼绑定 (Rigify)    → 带骨骼的蒙皮网格 (GLB)
```

> 动画生成阶段（HY-Motion 1.0 Lite）已跳过，需要 24GB VRAM。
用户输入: "一个穿铠甲的奇幻女战士，手持长剑"
              │
              ▼
┌─────────────────────────────────────────────┐
│  Stage 1: 文生图 (SDXL / SD3)               │  GPU Worker, ~10s
│  → 生成 2-4 张候选概念图                      │
│  → 用户选一张（或自动选最优）                  │  ← 唯一的用户交互点
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 2: 图生3D (TripoSR / Stable Fast 3D) │  GPU Worker, ~10s
│  → 输出 raw mesh (.glb)                      │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 3: 网格清理 (Instant Meshes + MeshLab)│  CPU Worker, ~5s
│  → 重拓扑、去退化面、修补孔洞                  │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 4: UV + 材质烘焙 (xatlas + bpy)      │  CPU Worker, ~30s
│  → UV展开 + PBR纹理烘焙                      │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 5: 骨骼绑定 (Rigify / UniRig)         │  CPU Worker, ~15s
│  → 自动绑定骨骼 + 蒙皮权重                    │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 6: 动画生成 (HY-Motion 1.0 Lite)      │  GPU Worker, ~20s
│  → 基于提示词生成动作                          │
│  → 或套用预设动作模板（idle/walk/run）         │
└──────────────────┬──────────────────────────┘
                   ▼
           最终资产 (.fbx + 纹理)
           → Web 3D预览 → Review → 发布
```

### 2D Art Pipeline

除了 3D 模型管线，平台同时支持独立的 2D 美术资源生成，用于游戏 UI 贴图、图标、立绘、卡牌插画等。

```
用户输入: "一把燃烧的传奇长剑图标，暗黑风格"
              │
              ▼
┌─────────────────────────────────────────────┐
│  Stage 1: 文生图 (SDXL)                      │  GPU Worker, ~10s
│  → 生成 2-4 张候选图                          │
│  → 用户选一张（或自动选最优）                  │  ← 复用 3D 管线同 Worker
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 2: 后处理                             │  CPU Worker, ~3s
│  → 去背景 (rembg / SAM)                      │
│  → 统一尺寸 / padding                        │
│  → 可选: 超分辨率 (Real-ESRGAN 2x/4x)        │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Stage 3: 格式产出                           │  CPU Worker, ~1s
│  → 单张 PNG (icon/portrait/card/background)  │
│  → 或 Sprite Sheet (多帧拼合 + JSON 坐标映射) │
│  → 或 9-Patch (带拉伸标记的 PNG)              │
└──────────────────┬──────────────────────────┘
                   ▼
           最终 2D 资产 (.png + 元数据)
           → Web 预览 → Review → 发布
```

**2D 管线用户参数：**

| 参数 | 选项 | 默认值 |
|------|------|--------|
| 用途类型 | icon / portrait / card / background / sprite | icon |
| 输出尺寸 | 64×64, 128×128, 256×256, 512×512, 1024×1024, 自定义 | 512×512 |
| 风格 | 写实 / 卡通 / 像素 / 暗黑 / 二次元 | 写实 |
| 去背景 | 是 / 否 | 是（icon/card 默认是，background 默认否） |
| 超分辨率 | 1x / 2x / 4x | 1x |

**与 3D 管线的关系：**
- 共享 Stage 1 的 SDXL Worker（文生图能力复用）
- 共享资产管理体系（版本、审批、权限、导出）
- `pipeline_runs` 表通过 `pipeline_type` 字段区分 `3d_scene` / `3d_character` / `2d_art`
- 独立的阶段处理器，互不影响

### Pipeline Stage Registry

**Design Decision**: All pipeline stage definitions live in a single Python module `backend/app/pipeline/pipeline_configs.py`.

- One `PIPELINE_REGISTRY` dict maps `pipeline_type` → ordered list of stages with their processors.
- `STAGE_DEFINITIONS` constant defines all 7 stages with available modes (mock/local/cloud) and mode→processor mapping.
- `get_processor_name_for_mode()` returns the correct processor name for a given stage + mode combination.
- `backend/app/pipeline/default_pipeline.py` is dead code and will be removed.
- API routes and frontend types must reference this registry, not hard-code stage lists.
- Stage IDs: `text_to_image`, `image_to_3d`, `mesh_cleanup`, `uv_material`, `rigging`, `animation` (3D); `text_to_image`, `post_process`, `format_output` (2D).
- Provider settings: `pipeline_defaults` stores default mode per pipeline type (mock/local/cloud/custom); `provider_settings` stores per-(pipeline_type, stage) overrides with cloud provider and api_key. Skip mode (`"skip"`) causes stage to be omitted from pipeline execution.

### UX: Single-Page Progressive Workflow

#### 3D 模式

```
┌──────────────────────────────────────────────────────────┐
│  [提示词输入框]                            [生成按钮]     │
│  [可选: 上传设计图]                                       │
│  资源类型: ◉ 3D 模型  ○ 2D 贴图                           │
├──────────┬───────────────────────────┬───────────────────┤
│          │                           │  管线时间线         │
│  参数    │      3D 预览画布          │  ● 文生图 ✓ 10s   │
│  面板    │      (React Three Fiber)  │  ● 3D生成 ✓ 10s   │
│          │                           │  ● 清理 ✓ 5s      │
│  风格    │   [旋转/缩放/线框/骨骼]    │  ◉ UV+材质... 30s │
│  选择    │                           │  ○ 绑定            │
│          │                           │  ○ 动画            │
│  输出    │                           │                   │
│  格式    │                           │  [编辑] [重试]     │
│          │                           │  （点击已完成阶段   │
│          │                           │   查看中间结果）    │
├──────────┴───────────────────────────┴───────────────────┤
│  [下载 FBX]  [下载 GLB]  [下载 Unity包]  [提交Review]    │
└──────────────────────────────────────────────────────────┘
```

#### 2D 贴图模式

```
┌──────────────────────────────────────────────────────────┐
│  [提示词输入框]                            [生成按钮]     │
│  [可选: 上传参考图]                                       │
│  资源类型: ○ 3D 模型  ◉ 2D 贴图                           │
├──────────┬───────────────────────────┬───────────────────┤
│          │                           │  管线时间线         │
│  参数    │      2D 图片预览          │  ● 文生图 ✓ 10s   │
│  面板    │      (透明棋盘格背景)      │  ◉ 后处理... 3s   │
│          │                           │  ○ 格式产出        │
│  用途    │   [缩放/原始尺寸/对比]     │                   │
│  icon    │   [去背景 前/后 切换]      │  [编辑] [重试]     │
│  portrait│                           │                   │
│  card    │                           │                   │
│  sprite  │                           │                   │
│          │                           │                   │
│  尺寸    │                           │                   │
│  512×512 │                           │                   │
│          │                           │                   │
│  去背景  │                           │                   │
│  超分辨率│                           │                   │
├──────────┴───────────────────────────┴───────────────────┤
│  [下载 PNG]  [下载 Sprite Sheet]  [下载 9-Patch]  [提交Review] │
└──────────────────────────────────────────────────────────┘
```

**Interaction Rules:**
1. Pipeline runs fully automatically after user clicks "Generate"
2. **Pause at Stage 1**: show 2-4 candidate concept images for user to pick (concept quality determines downstream quality)
3. Stages 2+ auto-advance, intermediate results available via polling (WebSocket [v2])
4. Any stage failure → show partial results, mark failed node, offer "retry from here"
5. Each completed stage has an "Edit" button for parameter adjustment or manual file upload

---

## Data Model

### Core Schema (PostgreSQL)

```sql
-- Users & Teams
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    settings JSONB DEFAULT '{}'
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID REFERENCES teams(id),
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin','artist','reviewer','viewer')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Assets
CREATE TABLE assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id),
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (
        'model_3d','texture_2d','sprite','material',
        'animation_clip','prefab','audio','vfx',
        'ui_icon','ui_portrait','ui_card','ui_background'
    ),
    source TEXT NOT NULL CHECK ('ai_generated','manual_upload','hybrid'),
    state TEXT NOT NULL DEFAULT 'draft' CHECK (
        'draft','processing','review','approved','rejected','published','deprecated'
    ),
    current_version INT NOT NULL DEFAULT 1,
    parent_asset_id UUID REFERENCES assets(id),
    metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Asset Versions (blob storage references)
CREATE TABLE asset_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id),
    version INT NOT NULL,
    storage_key TEXT NOT NULL,
    storage_key_thumbnail TEXT,
    file_format TEXT NOT NULL,
    file_size_bytes BIGINT,
    checksum_sha256 TEXT,
    source_type TEXT NOT NULL CHECK ('ai_pipeline','manual_upload','edited'),
    pipeline_run_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(asset_id, version)
);

> **Note**: `storage_key_thumbnail` is populated in [v2]. v1 does not generate thumbnails.

-- Asset Dependencies
CREATE TABLE asset_dependencies (
    dependent_asset_id UUID NOT NULL REFERENCES assets(id),
    dependency_asset_id UUID NOT NULL REFERENCES assets(id),
    dependency_type TEXT NOT NULL CHECK (
        'references_texture','references_material','references_rig','references_animation'
    ),
    PRIMARY KEY (dependent_asset_id, dependency_asset_id, dependency_type)
);

-- Pipeline Runs
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id),
    pipeline_type TEXT NOT NULL DEFAULT '3d_scene' CHECK (
        '3d_scene','3d_character','2d_art'
    ),
    prompt TEXT NOT NULL,
    reference_image_key TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        'pending','paused','running','completed','partial','failed'
    ),
    config JSONB NOT NULL,
    total_stages INT,
    completed_stages INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

> **Note**: `pipeline_type` is a first-class column (not in `config` JSON) because it's a core query dimension for filtering pipeline runs.

-- Pipeline Steps
CREATE TABLE pipeline_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID NOT NULL REFERENCES pipeline_runs(id),
    stage_order INT NOT NULL,
    stage TEXT NOT NULL,
    processor_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        'pending','running','completed','failed','skipped'
    ),
    input_artifact_ids UUID[] NOT NULL DEFAULT '{}',
    output_artifact_ids UUID[] NOT NULL DEFAULT '{}',
    config JSONB DEFAULT '{}',
    duration_ms INT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Artifacts (intermediate pipeline outputs) [v2: full artifact tracking]
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id),
    storage_key TEXT NOT NULL,
    file_format TEXT NOT NULL,
    file_size_bytes BIGINT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

> **Note**: The `artifacts` table is reserved for v2. In v1, intermediate outputs are tracked via `pipeline_steps.output_artifact_ids` JSON array.

-- Reviews
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id),
    version INT NOT NULL,
    reviewer_id UUID NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL CHECK ('approved','rejected','changes_requested'),
    notes TEXT,
    reviewed_at TIMESTAMPTZ DEFAULT now()
);
```

### State Machine

```
draft ──→ processing ──→ draft ──→ review ──→ approved ──→ published
              ▲              │                   │            │
              └──────────────┘                   ▼            ▼
                                           rejected    deprecated
                                              │            ▲
                                              ▼            │
                                           draft ──────────┘

Rules:
- ai_generated: must go draft → processing → review → approved → published
- manual_upload with artist/admin: can skip review, draft → approved → published
- reviewer: approval only, no direct publish
- viewer: read-only
- published → deprecated (admin only, soft delete, no hard delete)
- publish guard: all dependencies must also be published
- State transitions are validated via `is_valid_transition()` in the Asset model. Invalid transitions raise `ValueError`.
```

### Provider Settings

每个管线类型（3D 场景 / 3D 角色 / 2D）可独立配置默认运行模式，并支持按阶段覆盖。存储在 `pipeline_defaults` 和 `provider_settings` 两张表中。

```sql
-- 管线级别默认模式
CREATE TABLE pipeline_defaults (
    pipeline_type TEXT PRIMARY KEY,       -- "3d_scene", "3d_character", "2d_art"
    default_mode TEXT NOT NULL,           -- "mock", "local", "cloud", "custom"
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 按 (管线类型, 阶段) 的独立设置
CREATE TABLE provider_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_type TEXT NOT NULL,          -- 所属管线类型
    stage TEXT NOT NULL,                  -- e.g. "text_to_image"
    mode TEXT NOT NULL DEFAULT 'mock',    -- "mock", "local", "cloud", "skip"
    processor_name TEXT,                  -- 自动根据 mode 填充
    cloud_provider TEXT,                  -- e.g. "stability_ai", "tripo_cloud"
    api_key TEXT,                         -- 明文存储（内部工具）
    base_url TEXT,                        -- 可选，自定义 API 端点
    extra_config JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (pipeline_type, stage)         -- 每种管线类型有独立的阶段配置
);
```

**行为逻辑**：
- `default_mode == "custom"`：从 `provider_settings` 逐阶段读取 mode
- `default_mode != "custom"`：所有阶段使用 `default_mode` 作为 mode；cloud_provider/api_key 仍从 `provider_settings` 读取
- `mode == "skip"`：创建管线时跳过该阶段，不生成 PipelineStep

**阶段定义**（按管线类型分组，单一来源 `pipeline_configs.py`）：

| 管线类型 | 阶段 | 可用模式 |
|---------|------|---------|
| **3D 场景** | text_to_image | mock, local, cloud |
| | image_to_3d | mock, local, cloud |
| | mesh_cleanup | **skip**, mock, local |
| | uv_material | **skip**, mock, local |
| **3D 角色** | text_to_image | mock, local, cloud |
| | image_to_3d | mock, local, cloud |
| | mesh_cleanup | **skip**, mock, local |
| | uv_material | **skip**, mock, local |
| | rigging | **skip**, mock, local |
| **2D** | text_to_image | mock, local, cloud |
| | post_process | mock, local |
| | format_output | mock, local |

**API**：
- `GET /api/v1/settings/providers` — 返回按管线类型分组的 stage_definitions 和 defaults
- `PUT /api/v1/settings/providers/{pipeline_type}/{stage}` — 更新某管线类型的阶段设置
- `GET /api/v1/settings/providers/defaults` — 读取所有管线类型的默认模式
- `PUT /api/v1/settings/providers/defaults` — 更新某管线类型的默认模式

### Review Flow (v1)

- Asset owner submits for review (draft → review transition)
- Any team member with `reviewer` or `admin` role can approve/reject
- Single reviewer, single decision — no multi-reviewer arbitration in v1
- Review history is preserved in the `reviews` table

### Versioning

- Sequential integers (v1, v2, v3)
- Complete blob per version in object storage (no diffs)
- Rollback = create new version referencing old blob (preserves audit trail)
- Soft deprecation, never hard delete. Garbage collect blobs deprecated >90 days

---

## Tool Chain

### Recommended Free/Open-Source Tools

| 阶段 | 工具 | License | Notes |
|------|------|---------|-------|
| 文生图 | SDXL / SD3 | OpenRAIL | Stable Diffusion, self-hosted |
| 图生3D | TripoSR | MIT | 0.5s on A100, 6GB VRAM |
| 图生3D (增强) | Stable Fast 3D | Apache 2.0 | Built-in UV unwrapping |
| 网格清理 | Instant Meshes | BSD 3-Clause | Industry standard retopology |
| 网格修复 | PyMeshLab | MIT | Python bindings for MeshLab |
| UV展开 | xatlas | MIT | No dependencies, embeddable |
| 材质烘焙 | Blender (bpy) | GPLv3 | subprocess `blender --background --python`, file-based I/O |
| 骨骼绑定 | Rigify (Blender) | GPLv3 | Mature, well-documented |
| 骨骼绑定 (增强) | UniRig | Open | SIGGRAPH 2025, TripoSR team |
| 文本驱动动画 | HY-Motion 1.0 Lite | Apache 2.0 | 460M params, ~24GB VRAM |
| 动画库 | Mixamo | Free (web) | Thousands of free animations |
| 去背景 | rembg | MIT | U2-Net based, `pip install rembg` |
| 超分辨率 | Real-ESRGAN | BSD 3-Clause | 2x/4x upscale, `pip install realesrgan` |

### Deployment: Docker Containers

| Tool | Container Type | Resource | Integration |
|------|---------------|----------|-------------|
| SDXL/SD3 | Long-running GPU worker | 1 GPU (8-10GB) | `diffusers` + FastAPI wrapper |
| TripoSR/SF3D | Long-running GPU worker | 1 GPU (6-8GB) | Can time-share with SDXL |
| Instant Meshes | CPU worker | No GPU | Binary execution |
| xatlas | Embedded in Blender worker | No GPU | `pip install` or compile |
| Blender | subprocess (`blender --background --python`) | No GPU | Process isolation, thread-safe |
| Rigify/UniRig | Embedded in Blender worker | No GPU | Via bpy API |
| HY-Motion | Long-running GPU worker | 1 GPU (24GB) | Dedicated GPU, stays loaded |
| rembg | CPU worker (或共享 GPU worker) | 可选 GPU 加速 | `pip install rembg`, ONNX Runtime |
| Real-ESRGAN | CPU/GPU worker | 可选 GPU 加速 | `pip install realesrgan`, PyTorch |

### Blender Integration (subprocess)

**Design Decision**: Blender runs as an isolated subprocess, not in-process.

- **Why**: `import bpy` creates a global singleton that is not thread-safe. In a Celery worker with multiple tasks, concurrent bpy calls cause crashes. subprocess isolation guarantees safety.
- **How**: `BlenderBridge` class wraps `blender --background --python script.py`. Input/output via file system (JSON params in, .glb/.png out).
- **Fallback**: In local dev without Blender installed, fall back to `trimesh`-based pure Python processing (limited but functional).

### GPU Scheduling

```
Single GPU (e.g., 1x A100 80GB):
  Time-slice: Load SDXL → generate → unload → Load TripoSR → generate → unload → ...
  HY-Motion Lite (460M): fits alongside smaller models

Dual GPU (e.g., 2x A10G):
  GPU0: SDXL + TripoSR (round-robin, <10GB each)
  GPU1: HY-Motion (dedicated, 24GB, stays loaded)
```

### GPU Worker Configuration

**Design Decision**: Each GPU worker runs with `--pool=solo --concurrency=1`.

- **Why**: PyTorch model cache uses module-level variables + threading.Lock. This only works in a single-process model. Celery prefork creates separate processes where cache is not shared.
- **How**: One Celery worker per GPU, solo pool, concurrency=1. Models stay loaded in memory between tasks (no repeated loading).
- **Queue routing**: GPU tasks route to `gpu` queue, CPU tasks to `cpu` queue, pipeline orchestration to `pipeline` queue.
- **Scaling**: Add more GPUs = launch more workers, each bound to a specific GPU via `CUDA_VISIBLE_DEVICES`.

---

## 3D Web Viewer

### Tech: React Three Fiber + @react-three/drei

Features:
- GLB/glTF + FBX loading with DRACOLoader compression
- PBR material display (MeshStandardMaterial)
- Orbit controls (rotate/zoom/pan)
- Wireframe mode toggle
- Skeleton visualization (SkeletonHelper)
- Animation playback with timeline scrub (AnimationMixer.setTime)
- Side-by-side version comparison (dual Canvas, synced cameras)
- Metadata overlay (poly count, texture resolution, bone count)

Performance:
- Models >50K faces: server-side LOD preview, full model on demand
- 500K faces: BatchedMesh to reduce draw calls
- Draco geometry + KTX2 texture compression

> Server-side LOD and KTX2 compression are [v2] enhancements.

## 2D Asset Viewer

### Tech: Plain React + Canvas

Features:
- 透明棋盘格背景（预览去背景效果）
- 缩放 / 原始尺寸 / 适配窗口
- 去背景前后对比（左右滑动分割线）
- Sprite Sheet 帧播放 + 帧序号显示
- 9-Patch 拉伸标记可视化
- 多尺寸同屏对比（64 / 128 / 256 / 512 并排展示）
- 元数据叠加（尺寸、文件大小、DPI、用途类型）

> Sprite Sheet 帧播放 and 9-Patch 可视化 are [v2] features. v1 supports single PNG preview only.

---

## Unity Export

Unity is a **consumer only**, not part of the pipeline.

### Download Package Structure

```
AssetName/
├── Models/
│   └── AssetName.fbx           # With skeleton + animations
├── Textures/
│   ├── AssetName_Albedo.png
│   ├── AssetName_Normal.png
│   └── AssetName_MR.png        # Metalness + Roughness
└── README.txt                  # Import instructions
```

User drags into Unity `Assets/` directory. FBX is natively supported.
No `.unitypackage` generation needed for v1.

---

## Storage Strategy

| Data | Solution | Reason |
|------|----------|--------|
| Binary assets | MinIO → S3 | Large files, CDN distribution, content-addressable dedup |
| Metadata & relations | PostgreSQL | Tag search, dependency queries, version tracking |
| AI generation records | PostgreSQL + S3 | Params in DB, artifacts in object storage |
| Version history | S3 blob-per-version | Simple, reliable, garbage collect old versions |
| Team source files (.blend/.psd) | SVN or Git LFS (external) | Platform manages published assets only |
| Quota / cost tracking | TBD [v2] | Per-team generation limits and cost monitoring |

---

## CLI & MCP — AI-Friendly Interfaces

### Design Principle

The platform exposes three interfaces: **Web UI** (human), **REST API** (programs), **CLI** (developers/scripts), and **MCP** (AI agents). All four share the same backend service layer — no duplicated logic.

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Web UI     │  │  REST API    │  │    CLI       │  │  MCP Server  │
│  (React)     │  │  (FastAPI)   │  │   (typer)    │  │  (mcp SDK)   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┘
                                  │
                        ┌─────────▼─────────┐
                        │   Service Layer   │
                        │  (app/services/)  │
                        └─────────┬─────────┘
                                  │
                        ┌─────────▼─────────┐
                        │  DB + Storage     │
                        └───────────────────┘
```

### CLI (Command Line Interface)

A `typer`-based CLI for developers and automation scripts.

```bash
# Auth
artplatform login --email admin@artplatform.local
artplatform whoami

# Assets
artplatform assets list --state draft --type model_3d
artplatform assets create --name "Sword" --type model_3d
artplatform assets get <id>
artplatform assets upload <id> ./model.glb
artplatform assets download <id> --version 2 -o ./output/
artplatform assets export <id> --format unity -o ./export/

# Pipeline
artplatform pipeline run --prompt "a fantasy warrior" --reference ./ref.png
artplatform pipeline status <id> --watch
artplatform pipeline retry <id> --from-stage 3

# Reviews
artplatform reviews submit <asset-id> --version 2 --decision approved --notes "Looks good"
artplatform reviews list <asset-id>

# Teams
artplatform teams list
artplatform teams create --name "Art Team"
```

**Design decisions:**
- CLI calls the REST API via `httpx` (no direct DB access) — works against any deployed instance
- Token stored in `~/.artplatform/credentials` (file permission 600)
- `--output json` flag for scripting / piping to `jq`
- Interactive TUI for pipeline status with `rich` progress bars

### MCP Server (Model Context Protocol)

An MCP server that exposes platform capabilities as AI-callable tools. Enables AI coding assistants (Claude, Cursor, Copilot) to directly create, manage, and export art assets.

```
AI Agent (Claude / Cursor / Copilot)
       │
       │  MCP Protocol (stdio / SSE)
       ▼
┌─────────────────────────────────┐
│  ArtPlatform MCP Server         │
│                                 │
│  Tools:                         │
│  ├── generate_3d_asset()        │
│  ├── list_assets()              │
│  ├── get_asset()                │
│  ├── update_asset()             │
│  ├── upload_asset_version()     │
│  ├── export_asset()             │
│  ├── submit_review()            │
│  ├── run_pipeline()             │
│  └── get_pipeline_status()      │
│                                 │
│  Resources:                     │
│  ├── assets://recent            │
│  └── pipelines://{id}/timeline  │
│                                 │
│  Prompts:                       │
│  └── generate_asset_prompt      │
└────────────┬────────────────────┘
             │
             │  Direct service calls (in-process)
             ▼
┌─────────────────────────────────┐
│  FastAPI Service Layer          │
│  (same process or remote API)   │
└─────────────────────────────────┘
```

**Tool Definitions:**

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `generate_3d_asset` | `prompt`, `style?`, `reference_image_url?` | `pipeline_id` | Trigger full pipeline |
| `list_assets` | `state?`, `type?`, `search?`, `limit?` | `asset[]` | Browse/search assets |
| `get_asset` | `asset_id` | `asset_detail` | Full asset info with versions |
| `update_asset` | `asset_id`, `name?`, `tags?`, `state?` | `asset` | Update metadata or state |
| `upload_asset_version` | `asset_id`, `file_path` | `version` | Upload a file as new version |
| `export_asset` | `asset_id`, `format` | `download_url` | Export as unity/glb/fbx |
| `submit_review` | `asset_id`, `version`, `decision`, `notes?` | `review` | Approve/reject |
| `run_pipeline` | `prompt`, `config?` | `pipeline_id` | Start a pipeline run |
| `get_pipeline_status` | `pipeline_id` | `pipeline_status` | Check progress with step details |

**Prompt Template — `generate_asset_prompt`:**

Guides AI agents to construct effective prompts for the art pipeline, including style keywords, composition hints, and technical constraints (e.g., "low-poly game-ready", "PBR metallic-roughness workflow").

**Configuration (for AI tools):**

```json
// Claude Desktop: claude_desktop_config.json
{
  "mcpServers": {
    "artplatform": {
      "command": "python",
      "args": ["-m", "app.mcp"],
      "env": {
        "ARTPLATFORM_API_URL": "http://localhost:8000",
        "ARTPLATFORM_API_KEY": "..."
      }
    }
  }
}

// Cursor: .cursor/mcp.json
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

**Design decisions:**
- MCP server runs as a standalone Python process, communicates with backend via REST API
- Uses `httpx` for API calls (same as CLI) — works with any deployed instance
- No direct DB/storage access from MCP — all operations go through the same API surface
- Authentication via API key or JWT token
- Tool descriptions are optimized for AI comprehension (clear input/output schemas, usage examples)

---

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | React + TypeScript + Tailwind | Standard |
| 3D Preview | React Three Fiber + drei | React-native, richest ecosystem |
| Backend | Python FastAPI | AI ecosystem is Python-native |
| CLI | typer + rich + httpx | Type-hinted, modern, async-ready |
| MCP Server | mcp SDK (Python) | Standard MCP protocol for AI agents |
| Database | PostgreSQL + JSONB | Flexible metadata + relational queries |
| Object Storage | MinIO (dev) → S3 (prod) | S3-compatible API |
| Task Queue | Celery + Redis | GPU/CPU worker routing |
| Containers | Docker Compose (v1) → K8s (later) | Start simple |
| AI Inference | diffusers + custom workers | Python-native, Docker GPU passthrough |
| 3D Processing | Blender (subprocess) + xatlas + Instant Meshes | Process isolation, thread-safe |
| Animation | HY-Motion 1.0 Lite (460M, local) | Free, Apache 2.0, offline |

---

## Roadmap

### Phase 1 — MVP: Prompt → 3D Static Model + 2D Art (6-8 weeks)

```
Week 1-2: Infrastructure
  ├── FastAPI + PostgreSQL + MinIO + Redis
  ├── Docker Compose (all worker containers)
  └── Celery task queue framework

Week 3-4: Pipeline Stage 1-4 (3D) + Stage 1-3 (2D)
  ├── Stage 1: SDXL text-to-image (candidate concept images) [共享]
  ├── Stage 2: TripoSR image-to-3D
  ├── Stage 3: Instant Meshes cleanup
  ├── Stage 4: xatlas UV + Blender subprocess material baking
  ├── 2D Stage 2: rembg 去背景 + 尺寸标准化
  └── 2D Stage 3: PNG / Sprite Sheet / 9-Patch 产出

Week 5-6: Web UI
  ├── Single-page workflow UI (prompt + resource type switch + params + preview + timeline)
  ├── R3F 3D viewer (GLB, rotate/zoom, wireframe)
  ├── 2D image viewer (棋盘格背景, 缩放, 去背景对比)
  ├── WebSocket streaming of intermediate results
  └── Asset list page (browse, search, filter by 3D/2D type)

Week 7-8: Export + Review
  ├── FBX/GLB/Unity folder export (3D)
  ├── PNG / Sprite Sheet / 9-Patch export (2D)
  ├── Review approval workflow
  └── Basic RBAC permissions
```

### Phase 2 — Full Pipeline: Rig + Animation (4-6 weeks)

```
Week 1-2: Rigging
  ├── Rigify integration (bpy API)
  ├── UniRig integration (optional enhancement)
  └── Rig result 3D preview (skeleton visualization)

Week 3-4: Animation
  ├── HY-Motion 1.0 Lite integration
  ├── Preset motion templates (idle/walk/run/attack)
  └── Animation timeline playback/scrub

Week 5-6: Optimization
  ├── GPU worker pool scheduling
  ├── Pipeline stage parallelization
  └── Frontend caching and performance
```

### Phase 3 — Collaboration + AI Interfaces (ongoing)

```
  ├── CLI (typer-based, wraps REST API)
  │   ├── Auth (login, whoami)
  │   ├── Asset CRUD + upload/download
  │   ├── Pipeline run + status --watch
  │   └── Review submit
  ├── MCP Server (AI agent integration)
  │   ├── 9 tools (generate, list, get, update, upload, export, review, run_pipeline, pipeline_status)
  │   ├── Resources (recent assets, pipeline timelines)
  │   └── Prompt template (asset prompt construction guide)
  ├── Multi-version comparison (side-by-side 3D preview)
  ├── Team permissions (ABAC by project/category)
  ├── Concept image gallery (reuse generated images)
  ├── Manual upload flow (.blend/.psd source files)
  └── Open API (for external tools/pipelines)
```
