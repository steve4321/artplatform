# ArtPlatform

面向 Unity 3D 游戏开发的美术资源一站式生成管理平台。

## Features

- **Prompt-First**: 输入文字提示词，自动生成完整 3D 美术资源
- **Full Pipeline**: 文生图 → 3D建模 → 材质烘焙 → 骨骼绑定 → 动画生成
- **One-Stop Web Platform**: 浏览、预览、管理、审批，无需切换工具
- **3D Web Preview**: 浏览器内实时预览 3D 模型（旋转/缩放/线框/骨骼/动画）
- **Team Collaboration**: RBAC 权限、Review 审批流
- **Unity Ready**: 导出 FBX + 纹理，拖入 Unity 即可使用
- **CLI**: 命令行工具，支持脚本自动化和 CI/CD 集成
- **MCP**: Model Context Protocol 服务，AI 助手可直接调用平台能力

## Quick Start (Local Dev)

无需 Docker，零外部依赖：

```bash
cd backend
cp .env.example .env   # 设置 LOCAL_DEV=true

pip install -e ".[dev]"
LOCAL_DEV=true alembic upgrade head
LOCAL_DEV=true uvicorn app.main:app --reload
```

默认管理员: `admin@artplatform.local` / `admin123456`

## Architecture

详见 [docs/architecture.md](docs/architecture.md)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + Tailwind |
| 3D Preview | React Three Fiber + drei |
| Backend | Python FastAPI |
| CLI | typer + rich + httpx |
| MCP Server | mcp SDK (Python) |
| Database | PostgreSQL / SQLite (dev) |
| Object Storage | MinIO / S3 / Local (dev) |
| Task Queue | Celery + Redis / Eager (dev) |
| AI Models | SDXL, TripoSR, HY-Motion 1.0 |
| 3D Processing | Blender (bpy), xatlas, Instant Meshes |

## Status

🔨 Phase 1 开发中 — 后端 API + Auth + CRUD 已跑通，CLI + MCP 已实现
