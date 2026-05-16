# ArtPlatform

面向 Unity 3D 游戏开发的美术资源一站式生成管理平台。

## Features

- **Prompt-First**: 输入文字提示词，自动生成完整 3D 美术资源
- **Full Pipeline**: 文生图 → 3D建模 → 材质烘焙 → 骨骼绑定 → 动画生成
- **One-Stop Web Platform**: 浏览、预览、管理、审批，无需切换工具
- **3D Web Preview**: 浏览器内实时预览 3D 模型（旋转/缩放/线框/骨骼/动画）
- **Team Collaboration**: RBAC 权限、Review 审批流
- **Unity Ready**: 导出 FBX + 纹理，拖入 Unity 即可使用

## Architecture

详见 [docs/architecture.md](docs/architecture.md)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + Tailwind |
| 3D Preview | React Three Fiber + drei |
| Backend | Python FastAPI |
| Database | PostgreSQL |
| Object Storage | MinIO / S3 |
| Task Queue | Celery + Redis |
| AI Models | SDXL, TripoSR, HY-Motion 1.0 |
| 3D Processing | Blender (bpy), xatlas, Instant Meshes |

## Status

🚧 设计阶段 — 详见 [docs/architecture.md](docs/architecture.md)
