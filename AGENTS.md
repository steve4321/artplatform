# AGENTS.md — artplatform

## Project

面向 Unity 3D 游戏开发的美术资源一站式生成管理平台。

- 输入：文字提示词（可选设计图）
- 输出：生产级 3D 美术资源（建模 + 材质 + 蒙皮 + 动作）
- 形态：Web 平台，Unity 仅作为消费端

## Status

设计阶段。架构文档在 `docs/architecture.md`。尚未开始编码。

## Architecture

- Backend: Python FastAPI + PostgreSQL + MinIO + Redis + Celery
- Frontend: React + TypeScript + React Three Fiber
- AI Pipeline: SDXL → TripoSR → Instant Meshes → xatlas → Blender(bpy) → Rigify → HY-Motion
- 完整管线设计见 `docs/architecture.md`

## Key Design Decisions

- **提示词优先**：管线从文字提示词开始，不是从图片开始
- **一站式**：所有工具集成在后端，用户只看到 Web UI
- **Unity 仅消费**：不耦合到生产流程，只提供导出下载
- **工具透明**：底层工具链（ComfyUI/Blender 等）对用户不可见
- **bpy in-process**：`import bpy` 而非 subprocess 调用 Blender
- **Rigify/UniRig**：替代 AccuRIG（Windows-only，无 CLI）
