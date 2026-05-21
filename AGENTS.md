# AGENTS.md — artplatform

## Project

面向 Unity 3D 游戏开发的美术资源一站式生成管理平台。

- 输入：文字提示词（可选设计图）
- 输出：生产级 3D 美术资源（建模 + 材质 + 蒙皮 + 动作）
- 形态：Web 平台，Unity 仅作为消费端

## Status

开发阶段。后端 API + 前端 UI + CLI + MCP 已实现，使用 Mock 处理器。待接入真实 AI 模型。

## Architecture

- Backend: Python FastAPI + PostgreSQL + MinIO + Redis + Celery
- Frontend: React + TypeScript + React Three Fiber
- AI Pipeline: SDXL → TripoSR → Instant Meshes → xatlas → Blender(subprocess) → Rigify → HY-Motion
- 完整管线设计见 `docs/architecture.md`

## Key Design Decisions

- **提示词优先**：管线从文字提示词开始，不是从图片开始
- **一站式**：所有工具集成在后端，用户只看到 Web UI
- **Unity 仅消费**：不耦合到生产流程，只提供导出下载
- **工具透明**：底层工具链（ComfyUI/Blender 等）对用户不可见
- **Blender subprocess**：`blender --background --python script.py` 进程隔离，非 in-process（bpy 非线程安全）
- **Rigify/UniRig**：替代 AccuRIG（Windows-only，无 CLI）
- **GPU Worker 独占**：每个 GPU worker 使用 `--pool=solo --concurrency=1`，进程内模型缓存
- **pipeline_type 独立列**：核心查询维度，不放在 config JSON
- **概念图统一暂停**：所有 3D 管线（场景/角色）在概念图阶段统一暂停审核
- **管线阶段单一来源**：所有阶段定义统一在 `pipeline_configs.py`，不散落在多处
- **状态机验证**：状态转换必须通过 `is_valid_transition()` 验证
- **Provider 设置按管线类型独立**：3D 场景/3D 角色/2D 各有独立的默认模式和阶段覆盖，支持 `skip` 模式跳过不需要的阶段。`pipeline_defaults` 表存储每种管线类型的默认模式，`provider_settings` 表按 `(pipeline_type, stage)` 存储覆盖配置。创建管线时自动应用（优先级：API 显式配置 > 默认模式/DB 设置 > pipeline_configs 默认）
- **云 Provider 运行时注册**：cloud processor 从 step config 读取 `cloud_provider`/`api_key`，无需预配环境变量即可使用第三方 API
- **Setting 统一保存（无自动保存）**：Settings 页所有模式（local/cloud/mock）的每个管线类型下，各阶段配置统一通过该管线类型的"保存"按钮提交。保存顺序：各阶段设置（直接 API，不刷新）→ 默认模式 → 单次刷新结束。StageCard 使用 `forwardRef`/`useImperativeHandle` 暴露 `getPayload()`，由 PipelineSection 统一读取并保存。
