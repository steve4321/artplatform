# AI 模型接入方案

> ArtPlatform 管线 AI 模型集成详细方案 — 从概念验证到生产部署

## 概述

本文档为 ArtPlatform 6 阶段管线的每个 AI 模型提供 **三种接入路径**（云端 API / 自托管推理 / ComfyUI 集成），并给出代码示例、成本分析和分阶段实施计划。

### 设计原则

1. **渐进式接入**：Phase 1 用云端 API 验证管线，Phase 2 自托管降本，Phase 3 优化性能
2. **处理器隔离**：每个阶段一个独立 `PipelineProcessor` 实现，符合 `app/pipeline/processor.py` 的 ABC 接口
3. **统一接口**：所有处理器输入 `input_artifacts + config + output_dir`，输出 `list[dict]`，runner 负责上传
4. **可插拔切换**：通过 `processor_name` 配置选择实现（如 `sdxl_diffusers` / `sdxl_comfyui` / `sdxl_cloud`）
5. **Provider 抽象**：通过 `ModelProvider` ABC 解耦云 API 和自托管，换 Provider 不改 Processor 代码

---

## Provider 抽象架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PipelineProcessor (ABC)                     │
│     can_run() / run(input_artifacts, config, output_dir)          │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ 委托给 Provider
          ┌───────────────────┼────────────────────┐
          ▼                   ▼                    ▼
   ┌─────────────┐     ┌─────────────┐       ┌─────────────┐
   │ StabilityAI │     │   fal.ai   │  ... │  Replicate  │   ← 云 API
   └──────┬──────┘     └──────┬──────┘       └──────┬──────┘
          │                   │                    │
          └───────────────────┼────────────────────┘
                              ▼
              ┌───────────────────────────┐
              │     ModelProvider ABC     │  ← 统一抽象
              │  generate(params)          │
              │  estimate_cost(params)     │
              │  health_check()           │
              └────────────┬──────────────┘
                           │ 注册到 Router
                           ▼
              ┌───────────────────────────┐
              │     ProviderRouter        │
              │  primary + fallbacks 链    │
              │  cost_priority 策略        │
              └───────────────────────────┘
```

**核心价值**：
- 换 AI 提供商 → 只需改环境变量，不改 Processor 代码
- Provider 挂了 → Router 自动切换 Fallback，不影响管线
- 新增 Provider → 实现 `ModelProvider` ABC + 注册即可用

**三种运行模式**：

| 模式 | 环境变量 | GPU | AI 成本 | 用途 |
|------|---------|-----|--------|------|
| `mock` | `PROCESSOR_MODE=mock` | 无 | ¥0 | 开发测试 |
| `cloud` | `PROCESSOR_MODE=cloud` | 无 | 按量付费 | 初期验证 |
| `local` | `PROCESSOR_MODE=local` | 需要 | 电费 | 生产降本 |

**Provider 切换示例**：

```bash
# 换主 Provider（改一行 env）
TEXT_TO_IMAGE_PROVIDER=fal_ai

# 加 Fallback（逗号分隔）
TEXT_TO_IMAGE_FALLBACKS=replicate,stability_ai

# 成本优先路由
PROVIDER_COST_PRIORITY=true
```

---

## 目录

- [处理器接口规范](#处理器接口规范)
- [Stage 1: 文生图 (SDXL)](#stage-1-文生图-sdxl)
- [Stage 2: 图生 3D (TripoSR)](#stage-2-图生-3d-triposr)
- [Stage 3: 网格清理 (Instant Meshes)](#stage-3-网格清理-instant-meshes)
- [Stage 4: UV + 材质烘焙 (xatlas + bpy)](#stage-4-uv--材质烘焙-xatlas--bpy)
- [Stage 5: 骨骼绑定 (Rigify)](#stage-5-骨骼绑定-rigify)
- [Stage 6: 动画生成 (HY-Motion)](#stage-6-动画生成-hy-motion)
- [成本分析](#成本分析)
- [分阶段实施计划](#分阶段实施计划)
- [部署配置参考](#部署配置参考)

---

## 处理器接口规范

所有真实处理器必须继承 `PipelineProcessor` 并实现两个方法：

```python
# backend/app/pipeline/processor.py
class PipelineProcessor(ABC):
    stage: str              # e.g. "text_to_image"
    name: str               # e.g. "sdxl_diffusers"
    requires_gpu: bool      # 是否需要 GPU
    estimated_duration_s: int  # 预估耗时（秒）

    @abstractmethod
    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        """检查输入是否满足条件（如 image_to_3d 需要一张图片）"""
        ...

    @abstractmethod
    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        """执行处理，输出文件写入 output_dir，返回 artifact 描述列表"""
        ...
```

**输入 artifact 格式**（由 runner 下载后注入 `_local_path`）：

```python
{
    "storage_key": "pipelines/xxx/text_to_image/abc123.png",
    "file_format": "png",
    "_local_path": "/tmp/pipe_xxx/abc123.png",  # runner 注入
    "metadata": {"prompt": "...", "index": 0}
}
```

**输出 artifact 格式**（处理器返回，runner 负责上传）：

```python
{
    "local_path": "/tmp/pipe_xxx/output_0.png",
    "file_format": "png",
    "content_type": "image/png",
    "metadata": {"prompt": "...", "seed": 42}
}
```

---

## Stage 1: 文生图 (SDXL)

### 模型概要

| 属性 | 值 |
|------|-----|
| 模型 | Stable Diffusion XL 1.0 |
| 参数量 | 3.5B (UNet) + 2 text encoders |
| 模型文件 | ~6.94 GB (FP16) |
| VRAM 需求 | 8 GB (优化/Tiled VAE) — 22 GB (标准) |
| 输出 | 1024×1024 PNG |
| 推理时间 | 2-8s (RTX 4090) |
| 许可证 | CreativeML Open RAIL++-M |

### 方案 A: diffusers 自托管（推荐 Phase 2）

直接使用 HuggingFace `diffusers` 库，最大灵活性。

```python
# backend/app/workers/stage_processors/text_to_image.py
from __future__ import annotations

import logging
import os
from typing import Any

import torch
from diffusers import StableDiffusionXLPipeline

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

_pipe_cache: dict[str, StableDiffusionXLPipeline] = {}


def _get_pipeline(model_id: str = "stabilityai/stable-diffusion-xl-base-1.0",
                  device: str = "cuda") -> StableDiffusionXLPipeline:
    """Lazy-load pipeline with model caching to avoid repeated loading."""
    if model_id not in _pipe_cache:
        pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
        )
        pipe = pipe.to(device)
        # 优化: 启用 VAE slicing 和 attention slicing 降低 VRAM
        pipe.enable_vae_slicing()
        pipe.enable_attention_slicing()
        _pipe_cache[model_id] = pipe
    return _pipe_cache[model_id]


def _unload_pipeline(model_id: str) -> None:
    """从显存卸载模型（时分复用策略）。"""
    if model_id in _pipe_cache:
        del _pipe_cache[model_id]
        torch.cuda.empty_cache()
        logger.info("Unloaded SDXL pipeline from GPU")


@register
class SdxlDiffusersProcessor(PipelineProcessor):
    """SDXL via HuggingFace diffusers — self-hosted inference."""

    stage = "text_to_image"
    name = "sdxl_diffusers"
    requires_gpu = True
    estimated_duration_s = 10

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt"))

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        prompt = config["prompt"]
        negative_prompt = config.get("negative_prompt", "")
        num_images = config.get("num_images", 2)
        width = config.get("width", 1024)
        height = config.get("height", 1024)
        seed = config.get("seed")
        model_id = config.get("model_id", "stabilityai/stable-diffusion-xl-base-1.0")

        pipe = _get_pipeline(model_id)

        generator = None
        if seed is not None:
            generator = torch.Generator("cuda").manual_seed(seed)

        results = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_images_per_prompt=num_images,
            width=width,
            height=height,
            generator=generator,
            num_inference_steps=config.get("steps", 30),
            guidance_scale=config.get("guidance_scale", 7.5),
        )

        artifacts = []
        for i, image in enumerate(results.images):
            path = os.path.join(output_dir, f"concept_{i}.png")
            image.save(path, "PNG")
            artifacts.append({
                "local_path": path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "index": i,
                    "seed": seed + i if seed else None,
                    "generator": "sdxl_diffusers",
                    "model_id": model_id,
                },
            })

        # 时分复用: 生成后卸载以释放显存给下一阶段
        if config.get("unload_after", True):
            _unload_pipeline(model_id)

        logger.info("SDXL: generated %d images for prompt='%s...'", len(artifacts), prompt[:50])
        return artifacts
```

**依赖安装**：

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install diffusers transformers accelerate safetensors
```

### 方案 B: ComfyUI API（适合 Phase 2 可视化调试）

通过 ComfyUI 的 API 模式提交工作流，支持可视化编辑管线。

```python
# backend/app/workers/stage_processors/sdxl_comfyui.py
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

# ComfyUI 工作流 JSON — SDXL 标准文生图
SDXL_WORKFLOW = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "cfg": 7.5,
            "denoise": 1.0,
            "latent_image": ["5", 0],
            "model": ["4", 0],
            "negative": ["7", 0],
            "positive": ["6", 0],
            "sampler_name": "euler",
            "scheduler": "normal",
            "seed": 42,
            "steps": 30,
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sdxl_base_1.0.safetensors"},
    },
    "5": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 2, "height": 1024, "width": 1024}},
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["4", 1], "text": "PROMPT_PLACEHOLDER"},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"clip": ["4", 1], "text": "NEGATIVE_PLACEHOLDER"},
    },
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "artplatform", "images": ["8", 0]},
    },
}


def _queue_prompt(workflow: dict) -> str:
    """提交工作流到 ComfyUI 并返回 prompt_id。"""
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["prompt_id"]


def _wait_for_completion(prompt_id: str, timeout: int = 120) -> dict:
    """轮询 ComfyUI 直到任务完成。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        url = f"{COMFYUI_URL}/history/{prompt_id}"
        with urllib.request.urlopen(url) as resp:
            history = json.loads(resp.read())
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(1)
    raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {timeout}s")


@register
class SdxlComfyUIProcessor(PipelineProcessor):
    """SDXL via ComfyUI API — visual pipeline editor integration."""

    stage = "text_to_image"
    name = "sdxl_comfyui"
    requires_gpu = False  # GPU 在 ComfyUI 侧
    estimated_duration_s = 15

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt"))

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        prompt = config["prompt"]
        negative_prompt = config.get("negative_prompt", "")

        # 构建工作流
        workflow = json.loads(json.dumps(SDXL_WORKFLOW))
        workflow["6"]["inputs"]["text"] = prompt
        workflow["7"]["inputs"]["text"] = negative_prompt
        workflow["3"]["inputs"]["steps"] = config.get("steps", 30)
        workflow["3"]["inputs"]["cfg"] = config.get("guidance_scale", 7.5)
        if "seed" in config:
            workflow["3"]["inputs"]["seed"] = config["seed"]
        workflow["5"]["inputs"]["batch_size"] = config.get("num_images", 2)

        # 提交并等待
        prompt_id = _queue_prompt(workflow)
        result = _wait_for_completion(prompt_id)

        # 收集输出图片
        artifacts = []
        images_info = result.get("outputs", {}).get("9", {}).get("images", [])
        for img_info in images_info:
            filename = img_info["filename"]
            subfolder = img_info.get("subfolder", "")
            # 下载图片
            url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}"
            local_path = os.path.join(output_dir, filename)
            urllib.request.urlretrieve(url, local_path)
            artifacts.append({
                "local_path": local_path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {"prompt": prompt, "generator": "sdxl_comfyui"},
            })

        logger.info("SDXL ComfyUI: generated %d images", len(artifacts))
        return artifacts
```

**部署 ComfyUI**：

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt
# 下载 SDXL 模型到 models/checkpoints/
wget -P models/checkpoints/ https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
# 启动 API 模式
python main.py --listen 0.0.0.0 --port 8188
```

### 方案 C: 云端 API（推荐 Phase 1）

无需 GPU，按量付费，适合初期验证。

#### C1: Stability AI 官方 API

```python
# backend/app/workers/stage_processors/sdxl_cloud.py
from __future__ import annotations

import logging
import os

import httpx

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")
STABILITY_BASE_URL = "https://api.stability.ai/v1"


@register
class SdxlCloudProcessor(PipelineProcessor):
    """SDXL via Stability AI cloud API — no GPU needed."""

    stage = "text_to_image"
    name = "sdxl_cloud"
    requires_gpu = False
    estimated_duration_s = 5

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt")) and bool(STABILITY_API_KEY)

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        prompt = config["prompt"]
        negative_prompt = config.get("negative_prompt", "")
        num_images = config.get("num_images", 2)

        response = httpx.post(
            f"{STABILITY_BASE_URL}/generation/{config.get('engine', 'stable-diffusion-xl-1024-v1-0')}/text-to-image",
            headers={"Authorization": f"Bearer {STABILITY_API_KEY}"},
            json={
                "text_prompts": [
                    {"text": prompt, "weight": 1.0},
                    {"text": negative_prompt, "weight": -1.0},
                ],
                "cfg_scale": config.get("guidance_scale", 7.5),
                "steps": config.get("steps", 30),
                "width": config.get("width", 1024),
                "height": config.get("height", 1024),
                "samples": num_images,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        artifacts = []
        for i, img_data in enumerate(data["artifacts"]):
            import base64
            path = os.path.join(output_dir, f"concept_{i}.png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(img_data["base64"]))
            artifacts.append({
                "local_path": path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "prompt": prompt,
                    "index": i,
                    "seed": img_data.get("seed"),
                    "generator": "sdxl_cloud_stability",
                },
            })

        logger.info("SDXL Cloud: generated %d images via Stability API", len(artifacts))
        return artifacts
```

#### C2: fal.ai API（低延迟）

```python
# fal.ai 适配器 — WebSocket 流式推理，延迟更低
import fal_client  # pip install fal-client

result = fal_client.submit(
    "fal-ai/fast-sdxl",
    arguments={
        "prompt": "a fantasy warrior character, detailed armor",
        "negative_prompt": "blurry, low quality",
        "num_images": 2,
        "image_size": "square_hd",
    },
)
for i, image_url in enumerate(result["images"]):
    # 下载到 output_dir
    ...
```

**云端 API 价格对比**：

| 服务商 | 价格 | 特点 |
|--------|------|------|
| Stability AI | $0.003/张 | 官方 API，SDXL 专用 |
| Replicate | ~$0.002-0.01/张 | 多模型，按秒计费 |
| fal.ai | ~$0.005/张 | 低延迟 WebSocket，Fast SDXL |
| Together AI | $0.002/张 | 便宜，但队列可能排队 |

---

## Stage 2: 图生 3D (TripoSR)

### 模型概要

| 属性 | 值 |
|------|-----|
| 模型 | TripoSR (Stability AI + Tripo) |
| 参数量 | 0.46B |
| 模型文件 | ~1.68 GB |
| VRAM 需求 | 6 GB |
| 输入 | 单张 RGB 图片 |
| 输出 | OBJ 网格 + 顶点色 (NeRF 格式) |
| 推理时间 | <0.5s (A100), ~1s (RTX 3090) |
| 许可证 | MIT |
| 替代方案 | Stable Fast 3D (输出 GLB, ~0.5s) |

> **注意**：TripoSR 输出 OBJ + 顶点色，没有 UV 和 PBR 材质。需要后续阶段 (Stage 4) 处理。

### 方案 A: diffusers 自托管

```python
# backend/app/workers/stage_processors/image_to_3d.py
from __future__ import annotations

import logging
import os

import numpy as np
import torch
from tsr.models import TSR
from tsr.utils import remove_background

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

_model_cache: dict[str, TSR] = {}


def _get_model(device: str = "cuda") -> TSR:
    if "tripo_sr" not in _model_cache:
        model = TSR.from_pretrained(
            "stabilityai/TripoSR",
            config_name="config.json",
            weight_name="model.ckpt",
        )
        model.renderer.settings.chunk_size = 8192
        model.to(device)
        _model_cache["tripo_sr"] = model
    return _model_cache["tripo_sr"]


@register
class TripoSRProcessor(PipelineProcessor):
    """TripoSR — image-to-3D via single-image reconstruction."""

    stage = "image_to_3d"
    name = "tripo_sr"
    requires_gpu = True
    estimated_duration_s = 5

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(a.get("file_format") == "png" or a.get("content_type", "").startswith("image/")
                   for a in input_artifacts)

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        from PIL import Image

        # 取第一张图片
        image_artifact = next(
            (a for a in input_artifacts
             if a.get("file_format") in ("png", "jpg", "jpeg", "webp")
             or a.get("content_type", "").startswith("image/")),
            None,
        )
        if not image_artifact:
            raise ValueError("No image artifact found for image_to_3d")

        image_path = image_artifact["_local_path"]
        image = Image.open(image_path).convert("RGBA")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = _get_model(device)

        # 去背景（如果图片不透明）
        if config.get("remove_background", True):
            image = remove_background(image)

        # 推理
        with torch.no_grad():
            scenes = model([image], device=device)

        # 导出 OBJ
        mesh = scenes[0][0]  # 第一个场景的第一个 mesh
        obj_path = os.path.join(output_dir, "raw_mesh.obj")
        mesh.export(obj_path)

        # 也导出 GLB (给后续阶段用)
        glb_path = os.path.join(output_dir, "raw_mesh.glb")
        mesh.export(glb_path)

        # 时分复用卸载
        if config.get("unload_after", True) and "tripo_sr" in _model_cache:
            del _model_cache["tripo_sr"]
            torch.cuda.empty_cache()

        logger.info("TripoSR: generated 3D mesh from image")
        return [
            {
                "local_path": glb_path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {
                    "source_image": image_artifact.get("metadata", {}),
                    "generator": "tripo_sr",
                    "vertex_count": len(mesh.vertices),
                    "face_count": len(mesh.faces),
                },
            }
        ]
```

**安装 TripoSR**：

```bash
pip install git+https://github.com/VAST-AI-Research/TripoSR.git
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install rembg  # 背景去除
```

### 方案 B: Stable Fast 3D（替代方案）

Stable Fast 3D 的优势：直接输出 GLB 格式，速度快。

```python
# Stable Fast 3D 适配器
from stf3d import StableFast3D

model = StableFast3D.from_pretrained("stabilityai/stable-fast-3d")

# 输入图片 → 输出 GLB (含 UV + 纹理)
mesh_glb = model(image)  # 返回 trimesh.Trimesh 或 GLB bytes
```

> **推荐**：如果 Stable Fast 3D 成熟可用，优先于 TripoSR，因为它直接输出带 UV 的 GLB，可以简化 Stage 4。

### 方案 C: Tripo Cloud API

```python
import httpx

TRIPO_API_KEY = os.environ.get("TRIPO_API_KEY")

response = httpx.post(
    "https://api.tripo3d.ai/v2/openapi/task",
    headers={"Authorization": f"Bearer {TRIPO_API_KEY}"},
    json={
        "type": "image_to_model",
        "file": {"url": image_url},  # 需要先上传图片获取 URL
    },
)
task_id = response.json()["data"]["task_id"]

# 轮询结果
while True:
    status_resp = httpx.get(
        f"https://api.tripo3d.ai/v2/openapi/task/{task_id}",
        headers={"Authorization": f"Bearer {TRIPO_API_KEY}"},
    )
    if status_resp.json()["data"]["status"] == "success":
        model_url = status_resp.json()["data"]["output"]["model"]
        break
    time.sleep(2)
```

| 服务 | 价格 | 输出 |
|------|------|------|
| Tripo Cloud | ¥0.2-0.5/次 | GLB, 带纹理 |
| Meshy AI | ~$0.05/次 | GLB/FBX, 多种风格 |
| CSM AI | ~$0.03/次 | GLB, 带骨骼选项 |

---

## Stage 3: 网格清理 (Instant Meshes)

### 工具概要

| 属性 | 值 |
|------|-----|
| 工具 | Instant Meshes |
| 类型 | CPU (可 GPU 加速) |
| 功能 | 自动重拓扑、法线平滑 |
| 输入 | OBJ/GLB 网格 |
| 输出 | 重拓扑后的 OBJ/GLB |
| RAM 需求 | 4 GB+ |
| 安装方式 | 编译二进制 / pip (pyinstantmeshes) |

### 方案 A: pyinstantmeshes Python 绑定（推荐）

```python
# backend/app/workers/stage_processors/cleanup.py
from __future__ import annotations

import logging
import os

import pyinstantmeshes as im

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)


@register
class InstantMeshesProcessor(PipelineProcessor):
    """Instant Meshes — auto-retopology and mesh cleanup."""

    stage = "cleanup"
    name = "instant_meshes"
    requires_gpu = False
    estimated_duration_s = 5

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(a.get("file_format") in ("glb", "obj", "gltf", "fbx")
                   for a in input_artifacts)

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        import trimesh

        # 找到输入网格
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf")),
            None,
        )
        if not mesh_artifact:
            raise ValueError("No mesh artifact found for cleanup")

        input_path = mesh_artifact["_local_path"]
        mesh = trimesh.load(input_path, force="mesh")

        # Instant Meshes 重拓扑
        target_faces = config.get("target_faces", 10000)
        output_path = os.path.join(output_dir, "cleaned_mesh.glb")

        # 使用 pyinstantmeshes
        result = im.retopologize(
            mesh.vertices,
            mesh.faces,
            face_count=target_faces,
            smooth=config.get("smooth", True),
        )

        cleaned_mesh = trimesh.Trimesh(vertices=result.vertices, faces=result.faces)
        cleaned_mesh.export(output_path)

        logger.info(
            "Cleanup: %d→%d faces",
            len(mesh.faces),
            len(cleaned_mesh.faces),
        )
        return [
            {
                "local_path": output_path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {
                    "original_faces": len(mesh.faces),
                    "cleaned_faces": len(cleaned_mesh.faces),
                    "target_faces": target_faces,
                    "generator": "instant_meshes",
                },
            }
        ]
```

### 方案 B: CLI 子进程调用

如果 `pyinstantmeshes` 不可用，可以直接调用 Instant Meshes 的命令行工具：

```python
import subprocess

# Instant Meshes CLI
result = subprocess.run([
    "instant-meshes-cli",
    input_path,
    "-o", output_path,
    "-f", str(target_faces),    # 目标面数
    "-s",                       # 平滑
    "--deterministic",
], capture_output=True, text=True, timeout=60)
```

**编译安装**：

```bash
git clone https://github.com/wjakob/instant-meshes.git
cd instant-meshes
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
# 二进制在 build/instant-meshes-cli
```

### 方案 C: PyMeshLab（替代方案）

PyMeshLab 提供了更丰富的网格处理功能：

```python
import pymeshlab

ms = pymeshlab.MeshSet()
ms.load_new_mesh(input_path)

# 去除退化面
ms.apply_filter("meshing_remove_duplicate_vertices")
ms.apply_filter("meshing_remove_duplicate_faces")
ms.apply_filter("meshing_remove_null_faces")

# 简化到目标面数
ms.apply_filter("meshing_decimation_quadric_edge_collapse_with_texture",
                targetfacenum=target_faces)

# 补洞
ms.apply_filter("meshing_close_holes", maxholesize=30)

ms.save_current_mesh(output_path)
```

> **推荐**：`pyinstantmeshes` 做重拓扑 + `PyMeshLab` 做清理，组合使用。

---

## Stage 4: UV + 材质烘焙 (xatlas + bpy)

### 工具概要

| 工具 | 功能 | 安装方式 |
|------|------|---------|
| xatlas | 自动 UV 展开 | `pip install xatlas` (需编译) 或 Blender Smart UV Project |
| Blender (bpy) | 材质烘焙、网格处理 | `pip install bpy>=4.1.0` |
| PBR 纹理生成 | 从顶点色/颜色生成 PBR 贴图 | bpy 自定义脚本 |

### 方案 A: bpy + Smart UV Project（推荐）

使用 Blender 内置的 Smart UV Project 替代 xatlas（避免 C++ 编译依赖）。

```python
# backend/app/workers/stage_processors/uv_material.py
from __future__ import annotations

import logging
import os

import bpy

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)


def _setup_blender_headless():
    """配置 Blender 无头模式。"""
    # bpy 在导入时即启动 Blender 实例
    # 确保无 GUI
    if not bpy.app.background:
        import sys
        sys.argv = [sys.argv[0], "--background"]


@register
class UVBpyProcessor(PipelineProcessor):
    """UV unwrap + material baking via Blender (bpy)."""

    stage = "uv_material"
    name = "xatlas_bpy"
    requires_gpu = False
    estimated_duration_s = 30

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(a.get("file_format") in ("glb", "obj", "gltf", "fbx")
                   for a in input_artifacts)

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf")),
            None,
        )
        if not mesh_artifact:
            raise ValueError("No mesh artifact found for UV/material stage")

        input_path = mesh_artifact["_local_path"]
        texture_size = config.get("texture_resolution", 1024)

        # 清空默认场景
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        # 导入网格
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".glb":
            bpy.ops.import_scene.gltf(filepath=input_path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=input_path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=input_path)

        obj = bpy.context.selected_objects[0]
        bpy.context.view_layer.objects.active = obj

        # ── UV 展开 (Smart UV Project) ──
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(
            angle_limit=1.15192,  # 66°
            margin_method="SCALED",
            island_margin=0.02,
        )
        bpy.ops.object.mode_set(mode="OBJECT")

        # ── 创建 PBR 材质 ──
        mat = bpy.data.materials.new(name="ArtPlatform_PBR")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]

        # 从顶点色生成基础色纹理 (如果存在顶点色)
        if _has_vertex_colors(obj):
            _bake_vertex_color_to_texture(obj, mat, bsdf, output_dir, texture_size)

        obj.data.materials.append(mat)

        # ── 导出 GLB ──
        output_glb = os.path.join(output_dir, "uv_output.glb")
        bpy.ops.export_scene.gltf(
            filepath=output_glb,
            export_format="GLB",
            export_materials="EXPORT",
            export_textures=True,
            export_colors=True,
        )

        # ── 收集输出纹理 ──
        artifacts = [{
            "local_path": output_glb,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {"generator": "xatlas_bpy", "texture_resolution": texture_size},
        }]

        # 收集烘焙的纹理文件
        for tex_type in ("albedo", "normal", "metallic_roughness"):
            tex_path = os.path.join(output_dir, f"{tex_type}.png")
            if os.path.exists(tex_path):
                artifacts.append({
                    "local_path": tex_path,
                    "file_format": "png",
                    "content_type": "image/png",
                    "metadata": {"texture_type": tex_type},
                })

        logger.info("UV+Material: processed mesh with %d textures",
                     len(artifacts) - 1)
        return artifacts


def _has_vertex_colors(obj) -> bool:
    """检查对象是否有顶点色。"""
    if obj.data.color_attributes:
        return True
    return False


def _bake_vertex_color_to_texture(obj, mat, bsdf, output_dir: str, resolution: int):
    """将顶点色烘焙到 Albedo 纹理。"""
    import numpy as np
    from mathutils import Color

    # 创建纹理节点
    nodes = mat.node_tree.nodes
    tex_node = nodes.new("ShaderNodeTexImage")

    # 创建空白图像
    img = bpy.data.images.new("albedo_bake", width=resolution, height=resolution)
    img.filepath = os.path.join(output_dir, "albedo.png")

    # 设置烘焙目标
    tex_node.image = img
    for area in bpy.context.screen.areas:
        if area.type == "IMAGE_EDITOR":
            area.spaces.active.image = img

    # 烘焙顶点色
    bpy.context.scene.cycles.bake_type = "DIFFUSE"
    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_pass_color = True

    mat.node_tree.nodes.active = tex_node
    bpy.ops.object.bake(type="DIFFUSE")

    # 保存
    img.file_format = "PNG"
    img.save()

    # 连接到 BSDF
    nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)
```

**安装 bpy**：

```bash
pip install bpy>=4.1.0
# bpy 是 Blender 的 Python 绑定，4.1+ 版本以 pip 包形式分发
# 注意: bpy 与系统安装的 Blender 冲突，建议只用 pip 版本
```

### 方案 B: xatlas UV 展开（高级）

如果需要更精确的 UV 展开，可以使用 xatlas：

```python
import xatlas
import trimesh
import numpy as np

# 加载网格
mesh = trimesh.load(input_path, force="mesh")

# xatlas UV 展开
atlas = xatlas.Atlas()
atlas.add_mesh(mesh.vertices, mesh.faces)
atlas.generate(
    chart_options=xatlas.ChartOptions(max_iterations=100),
    pack_options=xatlas.PackOptions(padding=2, resolution=2048),
)

vmapping, indices, uvs = atlas[0]  # 顶点映射、新索引、UV 坐标

# 构建带 UV 的新网格
new_mesh = trimesh.Trimesh(
    vertices=mesh.vertices[vmapping],
    faces=indices,
    visual=trimesh.visual.TextureVisuals(uv=uvs),
)
```

> **xatlas 安装问题**：xatlas 没有 pip wheel，需要本地编译（C++），在 Linux 上需要 CMake + gcc。如果编译困难，使用方案 A 的 Smart UV Project。

---

## Stage 5: 骨骼绑定 (Rigify)

### 工具概要

| 属性 | 值 |
|------|-----|
| 工具 | Rigify (Blender 内置) |
| 类型 | CPU |
| 功能 | 自动绑定人形骨骼 + 蒙皮权重 |
| 输入 | GLB/OBJ 网格 |
| 输出 | 带骨骼的 GLB/FBX |
| RAM 需求 | 8 GB+ |
| 前提 | 网格需近似人形 |

### 方案: Rigify via bpy

```python
# backend/app/workers/stage_processors/rig.py
from __future__ import annotations

import logging
import os

import bpy

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

# Rigify 元骨骼定义 — 人形标准骨骼
RIGIFY_META_BONES = {
    "head": {"position": (0, 0, 1.6), "parent": "spine_03"},
    "spine_01": {"position": (0, 0, 0.9)},
    "spine_02": {"position": (0, 0, 1.1), "parent": "spine_01"},
    "spine_03": {"position": (0, 0, 1.3), "parent": "spine_02"},
    "pelvis": {"position": (0, 0, 0.85), "parent": "spine_01"},
    "upper_arm_l": {"position": (0.2, 0, 1.3), "parent": "spine_03"},
    "upper_arm_r": {"position": (-0.2, 0, 1.3), "parent": "spine_03"},
    "forearm_l": {"position": (0.5, 0, 1.3), "parent": "upper_arm_l"},
    "forearm_r": {"position": (-0.5, 0, 1.3), "parent": "upper_arm_r"},
    "thigh_l": {"position": (0.1, 0, 0.85), "parent": "pelvis"},
    "thigh_r": {"position": (-0.1, 0, 0.85), "parent": "pelvis"},
    "shin_l": {"position": (0.1, 0, 0.45), "parent": "thigh_l"},
    "shin_r": {"position": (-0.1, 0, 0.45), "parent": "thigh_r"},
    "foot_l": {"position": (0.1, 0.1, 0.05), "parent": "shin_l"},
    "foot_r": {"position": (-0.1, 0.1, 0.05), "parent": "shin_r"},
}


@register
class RigifyProcessor(PipelineProcessor):
    """Rigify auto-rigging via Blender bpy."""

    stage = "rig"
    name = "rigify"
    requires_gpu = False
    estimated_duration_s = 15

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(a.get("file_format") in ("glb", "obj", "gltf", "fbx")
                   for a in input_artifacts)

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf")),
            None,
        )
        if not mesh_artifact:
            raise ValueError("No mesh artifact for rigging")

        input_path = mesh_artifact["_local_path"]

        # 清空场景
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        # 导入网格
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".glb":
            bpy.ops.import_scene.gltf(filepath=input_path)
        elif ext == ".obj":
            bpy.ops.wm.obj_import(filepath=input_path)

        obj = bpy.context.selected_objects[0]

        # ── 自动估算骨骼位置 ──
        bone_positions = _estimate_bone_positions(obj, config)

        # ── 创建 Rigify 元骨骼 ──
        armature = _create_meta_rig(bone_positions)
        bpy.context.view_layer.objects.active = armature

        # ── 生成 Rigify 骨骼 ──
        bpy.ops.pose.rigify_generate()

        # 找到生成的 rig
        rig = None
        for o in bpy.context.scene.objects:
            if o.type == "ARMATURE" and o != armature:
                rig = o
                break

        if not rig:
            raise RuntimeError("Rigify generation failed")

        # ── 绑定蒙皮权重 ──
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")

        # ── 导出 ──
        output_path = os.path.join(output_dir, "rigged_model.glb")
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format="GLB",
            export_materials="EXPORT",
            export_skins=True,
            export_bones="EXPORT",
        )

        # 也导出 FBX (Unity 友好)
        fbx_path = os.path.join(output_dir, "rigged_model.fbx")
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            use_selection=False,
            armature_type="EXPORT",
            bake_anim=True,
        )

        bone_count = len(rig.data.bones) if rig else 0
        logger.info("Rigify: auto-rigged with %d bones", bone_count)

        artifacts = [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "bone_count": bone_count,
                "generator": "rigify",
            },
        }]

        if os.path.exists(fbx_path):
            artifacts.append({
                "local_path": fbx_path,
                "file_format": "fbx",
                "content_type": "application/octet-stream",
                "metadata": {"format": "unity_fbx"},
            })

        return artifacts


def _estimate_bone_positions(obj, config: dict) -> dict:
    """根据网格包围盒估算骨骼位置。

    策略：将网格归一化到标准人形骨骼模板，通过缩放和偏移适配。
    """
    import numpy as np
    from mathutils import Vector

    # 获取网格包围盒
    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_co = Vector((min(b.x for b in bbox), min(b.y for b in bbox), min(b.z for b in bbox)))
    max_co = Vector((max(b.x for b in bbox), max(b.y for b in bbox), max(b.z for b in bbox)))
    center = (min_co + max_co) / 2
    height = max_co.z - min_co.z

    # 将元骨骼模板缩放到网格尺寸
    positions = {}
    for bone_name, template in RIGIFY_META_BONES.items():
        # 模板中的 Y 值当作归一化高度 (0-1.6)
        normalized = template["position"]
        scaled = (
            center.x + normalized[0] * height / 1.6,
            center.y + normalized[1] * height / 1.6,
            min_co.z + normalized[2] / 1.6 * height,
        )
        positions[bone_name] = scaled

    return positions


def _create_meta_rig(bone_positions: dict):
    """创建 Rigify 元骨骼。"""
    bpy.ops.object.armature_add()
    armature = bpy.context.active_object
    armature.name = "META-RIG"

    bpy.ops.object.mode_set(mode="EDIT")

    # 删除默认骨骼，创建自定义骨骼
    for bone in armature.data.edit_bones:
        armature.data.edit_bones.remove(bone)

    edit_bones = armature.data.edit_bones
    created_bones = {}

    for bone_name, pos in bone_positions.items():
        b = edit_bones.new(bone_name)
        b.head = pos
        b.tail = (pos[0], pos[1], pos[2] + 0.1)  # 向上偏移
        created_bones[bone_name] = b

    # 设置父子关系
    for bone_name, template in RIGIFY_META_BONES.items():
        if "parent" in template and bone_name in created_bones:
            parent_name = template["parent"]
            if parent_name in created_bones:
                created_bones[bone_name].parent = created_bones[parent_name]

    bpy.ops.object.mode_set(mode="OBJECT")

    # 标记为 Rigify 元骨骼
    armature.data["rigify_type"] = "basic_human"

    return armature
```

**备选方案：UniRig**（更适合非人形角色）：

```python
# UniRig — 基于学习的自动绑定
# 适用于任意形态的角色（动物、怪物等）
from unirig import UniRigPipeline

pipeline = UniRigPipeline.from_pretrained("autumnbud/UniRig")
result = pipeline(mesh_path=input_path)
result.export(output_path, format="glb")
```

> **建议**：人形角色用 Rigify（稳定、骨骼标准），非人形用 UniRig（泛化好）。通过 `config.processor_name` 切换。

---

## Stage 6: 动画生成 (HY-Motion)

### 模型概要

| 属性 | 值 |
|------|-----|
| 模型 | HY-Motion 1.0 Lite |
| 参数量 | 0.46B |
| VRAM 需求 | **24 GB** |
| 输入 | 骨骼 + 文字提示词 |
| 输出 | BVH 动作文件 |
| 推理时间 | 10-30s |
| 许可证 | Apache 2.0 |
| 替代方案 | Mixamo 预设动作 / 自定义 bpy 动画 |

### 方案 A: HY-Motion 自托管（推荐 Phase 2）

```python
# backend/app/workers/stage_processors/animate.py
from __future__ import annotations

import logging
import os

import torch

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

_hymotion_cache = {}


def _get_hymotion_model(device: str = "cuda"):
    """Lazy-load HY-Motion model."""
    if "hy_motion" not in _hymotion_cache:
        from hymotion.models import HYMotionPipeline

        pipeline = HYMotionPipeline.from_pretrained(
            "hymotion/HY-Motion-1.0-Lite",
            torch_dtype=torch.float16,
        )
        pipeline = pipeline.to(device)
        _hymotion_cache["hy_motion"] = pipeline
    return _hymotion_cache["hy_motion"]


@register
class HYMotionProcessor(PipelineProcessor):
    """HY-Motion — text-driven motion generation for rigged characters."""

    stage = "animate"
    name = "hy_motion"
    requires_gpu = True
    estimated_duration_s = 25

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        has_mesh = any(a.get("file_format") in ("glb", "fbx") for a in input_artifacts)
        has_prompt = bool(config.get("animation_prompt") or config.get("prompt"))
        return has_mesh and has_prompt

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        import bpy

        # 找到带骨骼的网格
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "fbx")),
            None,
        )
        if not mesh_artifact:
            raise ValueError("No rigged mesh for animation")

        input_path = mesh_artifact["_local_path"]
        prompt = config.get("animation_prompt", config.get("prompt", "idle pose"))

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = _get_hymotion_model(device)

        # ── 生成 BVH 动作 ──
        with torch.no_grad():
            motion = model(
                prompt=prompt,
                num_frames=config.get("num_frames", 60),
                fps=config.get("fps", 30),
                guidance_scale=config.get("guidance_scale", 7.5),
            )

        # 保存 BVH
        bvh_path = os.path.join(output_dir, "motion.bvh")
        motion.save_bvh(bvh_path)

        # ── 通过 bpy 将 BVH 应用到骨骼网格 ──
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        # 导入带骨骼的网格
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".glb":
            bpy.ops.import_scene.gltf(filepath=input_path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=input_path)

        # 导入 BVH 动作
        bpy.ops.import_anim.bvh(filepath=bvh_path)

        # ── 导出带动画的最终模型 ──
        output_glb = os.path.join(output_dir, "animated_output.glb")
        bpy.ops.export_scene.gltf(
            filepath=output_glb,
            export_format="GLB",
            export_animations=True,
            export_skins=True,
        )

        output_fbx = os.path.join(output_dir, "animated_output.fbx")
        bpy.ops.export_scene.fbx(
            filepath=output_fbx,
            bake_anim=True,
            armature_type="EXPORT",
        )

        # 卸载 HY-Motion
        if config.get("unload_after", True) and "hy_motion" in _hymotion_cache:
            del _hymotion_cache["hy_motion"]
            torch.cuda.empty_cache()

        logger.info("HY-Motion: generated animation for '%s'", prompt[:50])

        artifacts = [
            {
                "local_path": output_glb,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {
                    "animation_prompt": prompt,
                    "animation_clips": 1,
                    "num_frames": config.get("num_frames", 60),
                    "fps": config.get("fps", 30),
                    "generator": "hy_motion",
                },
            },
            {
                "local_path": output_fbx,
                "file_format": "fbx",
                "content_type": "application/octet-stream",
                "metadata": {"format": "unity_fbx_with_animation"},
            },
        ]

        return artifacts
```

**安装 HY-Motion**：

```bash
pip install git+https://github.com/chingspy/HY-Motion.git
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 方案 B: Mixamo 预设动作（低成本备选）

不需要 GPU，通过预设动作模板直接应用到骨骼。

```python
@register
class MixamoPresetProcessor(PipelineProcessor):
    """预设动作模板 — idle/walk/run/jump 等。"""

    stage = "animate"
    name = "mixamo_preset"
    requires_gpu = False
    estimated_duration_s = 5

    # 内置动作预设 (BVH 文件路径)
    PRESETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "presets")

    def can_run(self, input_artifacts, config):
        has_mesh = any(a.get("file_format") in ("glb", "fbx") for a in input_artifacts)
        has_preset = bool(config.get("animation_preset"))
        return has_mesh and has_preset

    def run(self, input_artifacts, config, output_dir):
        import bpy

        preset = config.get("animation_preset", "idle")
        preset_bvh = os.path.join(self.PRESETS_DIR, f"{preset}.bvh")

        if not os.path.exists(preset_bvh):
            raise FileNotFoundError(f"Preset '{preset}' not found")

        # 导入网格 → 导入 BVH → 合并 → 导出
        # (实现类似 HYMotionProcessor 的 bpy 流程)
        ...
```

**预设动作来源**：

| 来源 | 动作数 | 格式 | 说明 |
|------|--------|------|------|
| Mixamo (Adobe) | 2000+ | FBX | 免费账号可下载，需手动转 BVH |
| CMU Motion Capture | 2500+ | BVH | 公开领域，研究用途 |
| Lafan1 | 500+ | BVH | 高质量，适合游戏 |
| 自建库 | 自定义 | BVH | 手动 K 帧或动捕 |

> **建议**：Phase 1 用预设动作（零成本），Phase 2 接入 HY-Motion（AI 生成），同时保留预设作为 fallback。

### 方案 C: 云端 API

目前没有成熟的 motion generation 云端 API，但可以：

1. **自建 API**：在云 GPU 上部署 HY-Motion，通过 HTTP 调用
2. **Replicate**：未来可能有人部署 HY-Motion 模型

```python
# 自建 HY-Motion API 的客户端
response = httpx.post(
    f"{HY_MOTION_API_URL}/generate",
    json={"prompt": "walking", "num_frames": 60},
    timeout=60,
)
bvh_data = response.content
```

---

## 成本分析

### 云 GPU 租赁价格（中国）

| 平台 | GPU | 价格 (¥/小时) | 特点 |
|------|-----|--------------|------|
| **AutoDL** | RTX 3090 (24GB) | ¥2.0-3.0 | 最低价，社区镜像丰富 |
| **AutoDL** | A100 (40GB) | ¥5.0-7.0 | 大显存，推荐 |
| **Featurize** | RTX 3090 | ¥2.8 | 界面友好 |
| **GPUSHARE** | RTX 3090 | ¥3.5 | 稳定 |
| **恒源云** | RTX 3090 | ¥2.5 | 新平台 |
| **矩池云** | RTX 3090 | ¥3.0 | 学术优惠 |

### 云 GPU 租赁价格（海外）

| 平台 | GPU | 价格 ($/小时) | 特点 |
|------|-----|-------------|------|
| **RunPod** | RTX 3090 | $0.22 | 便宜 |
| **RunPod** | A100 (40GB) | $0.70 | 推荐自托管 |
| **Vast.ai** | RTX 3090 | $0.15-0.30 | 最便宜，但稳定性差 |
| **AWS g5.xlarge** | A10G (24GB) | $1.006 | 稳定，企业级 |
| **GCP a2-highgpu-1g** | A100 (40GB) | $3.67 | 贵但可靠 |
| **Lambda Labs** | A100 (40GB) | $0.55 | 性价比高 |

### 自托管 vs 云 API 成本对比

**场景假设**：日生成 50 个角色，每个角色耗时 ~75s

| 方案 | 月成本 (¥) | 前置投入 | 优点 | 缺点 |
|------|-----------|---------|------|------|
| **Stability API + Tripo Cloud** | ¥600-1000 | 无 | 零运维 | 依赖第三方 |
| **AutoDL RTX 3090 (按需)** | ¥900-1500 | 无 | 灵活 | 网络延迟 |
| **AutoDL A100 (包月)** | ¥3000-5000 | 无 | 稳定 | 成本固定 |
| **自购 RTX 4090** | 电费 ~¥200/月 | ¥13000 | 长期最便宜 | 前期投入大 |
| **自购 A100 40GB** | 电费 ~¥300/月 | ¥50000+ | 企业级 | 极高投入 |

### 单次生成成本估算

| 阶段 | 云 API | 自托管 (RTX 3090 @¥2.5/hr) |
|------|--------|--------------------------|
| 1. 文生图 (SDXL) | ¥0.02 (Stability API) | ¥0.01 (10s) |
| 2. 图生3D (TripoSR) | ¥0.3 (Tripo Cloud) | ¥0.001 (1s) |
| 3. 网格清理 | — | — (CPU) |
| 4. UV+材质 | — | — (CPU) |
| 5. 骨骼绑定 | — | — (CPU) |
| 6. 动画 (HY-Motion) | — (无云API) | ¥0.02 (30s) |
| **总计** | **¥0.32** | **¥0.03** |

> **结论**：自托管的单次成本远低于云 API，但需要 GPU 硬件。推荐 Phase 1 用云 API 验证，Phase 2 自托管降本。

---

## 分阶段实施计划

### Phase 1: 云端 API 接入 (1-2 周)

**目标**：验证完整管线逻辑，无 GPU 依赖。

| 任务 | 方案 | 优先级 |
|------|------|--------|
| Stage 1 文生图 | Stability AI API | P0 |
| Stage 2 图生3D | Tripo Cloud API | P0 |
| Stage 3 网格清理 | PyMeshLab (CPU) | P0 |
| Stage 4 UV+材质 | bpy Smart UV Project (CPU) | P0 |
| Stage 5 骨骼绑定 | Rigify via bpy (CPU) | P0 |
| Stage 6 动画 | Mixamo 预设 BVH (CPU) | P0 |

**实现清单**：
- [ ] 创建 6 个真实处理器文件 (`text_to_image.py`, `image_to_3d.py`, ...)
- [ ] 每个处理器实现 `can_run()` + `run()`
- [ ] 在 `__init__.py` 中注册（根据 `PROCESSOR_MODE` 环境变量选择 mock/real）
- [ ] 添加配置项：API keys、模型路径、预设目录
- [ ] 更新 `.env.example` 添加云 API key 配置
- [ ] 端到端测试：创建管线 → 云 API 调用 → 验证输出
- [ ] 准备 Mixamo 预设 BVH 文件（idle, walk, run, jump）

**Phase 1 架构调整**：

```python
# backend/app/workers/stage_processors/__init__.py
import os

_MODE = os.environ.get("PROCESSOR_MODE", "mock").lower()

if _MODE == "mock":
    import app.workers.stage_processors.mock
elif _MODE == "cloud":
    from . import text_to_image, image_to_3d, cleanup, uv_material, rig, animate
elif _MODE == "local":
    from . import text_to_image, image_to_3d, cleanup, uv_material, rig, animate
```

### Phase 2: 自托管推理 (2-4 周)

**目标**：在 GPU 服务器上部署全部模型，降低成本。

| 任务 | 方案 | 优先级 |
|------|------|--------|
| GPU 服务器搭建 | AutoDL / 自购 RTX 3090 | P0 |
| SDXL diffusers 部署 | 方案 A (diffusers) | P0 |
| TripoSR 部署 | 方案 A (diffusers) | P0 |
| Instant Meshes 部署 | pyinstantmeshes | P1 |
| xatlas UV 展开 | bpy Smart UV Project | P1 |
| Rigify 自动绑定 | bpy Rigify | P1 |
| HY-Motion 部署 | 方案 A (自托管) | P0 |
| 显存时分复用 | load→run→unload 策略 | P0 |

**Phase 2 实现清单**：
- [ ] 模型下载脚本 (`scripts/download_models.sh`)
- [ ] GPU Worker Docker 镜像构建
- [ ] 显存管理器（统一 load/unload 逻辑）
- [ ] 推理性能基准测试
- [ ] 错误恢复和重试机制
- [ ] 模型热加载（不重启 Worker 即可更新模型）

**模型下载脚本**：

```bash
#!/bin/bash
# scripts/download_models.sh

set -e
MODEL_DIR="${MODEL_DIR:-./models}"

mkdir -p "$MODEL_DIR"

echo "Downloading SDXL..."
python -c "
from diffusers import StableDiffusionXLPipeline
StableDiffusionXLPipeline.from_pretrained(
    'stabilityai/stable-diffusion-xl-base-1.0',
    torch_dtype=torch.float16,
    variant='fp16',
    cache_dir='$MODEL_DIR/sdxl',
)
"

echo "Downloading TripoSR..."
git lfs install
git clone https://huggingface.co/stabilityai/TripoSR "$MODEL_DIR/triposr"

echo "Downloading HY-Motion..."
git clone https://huggingface.co/hymotion/HY-Motion-1.0-Lite "$MODEL_DIR/hy-motion"

echo "All models downloaded to $MODEL_DIR"
du -sh "$MODEL_DIR"/*
```

### Phase 3: 性能优化 (2-4 周)

**目标**：降低延迟，提高吞吐量。

| 优化项 | 方法 | 预期提升 |
|--------|------|---------|
| SDXL 加速 | TensorRT / xFormers / DeepCache | 2-3x |
| TripoSR 加速 | ONNX Runtime / TorchScript | 1.5x |
| HY-Motion 加速 | Flash Attention 2 / 模型蒸馏 | 2x |
| 管线并行 | GPU + CPU 阶段流水线执行 | 1.5x 总吞吐 |
| 批量推理 | 多请求批处理 SDXL | 3-5x 吞吐 |
| 模型缓存 | SSD 热模型缓存 / CPU offload | 减少加载时间 |
| ComfyUI 集成 | 统一推理引擎 | 运维简化 |

**Phase 3 架构：多 Worker 并行**：

```
                    ┌─────────────────────┐
                    │   FastAPI Server     │
                    │   (API + 调度)        │
                    └──────┬──────────────┘
                           │ Celery Queue
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ GPU Worker │ │ GPU Worker │ │ CPU Worker │
     │ SDXL       │ │ HY-Motion  │ │ InstantMesh│
     │ TripoSR    │ │ (常驻)     │ │ xatlas+bpy │
     │ (轮流加载) │ │            │ │ Rigify     │
     └────────────┘ └────────────┘ └────────────┘
```

---

## 部署配置参考

### 环境变量

```bash
# ── 通用 ──
PROCESSOR_MODE=cloud    # mock | cloud | local
LOCAL_DEV=false

# ── 云 API Keys (Phase 1) ──
STABILITY_API_KEY=sk-xxx
TRIPO_API_KEY=xxx
FAL_API_KEY=xxx

# ── 自托管配置 (Phase 2) ──
CUDA_DEVICE=cuda:0
MODEL_CACHE_DIR=/data/models
SDXL_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0
TRIPOSR_MODEL_PATH=/data/models/triposr
HYMOTION_MODEL_PATH=/data/models/hy-motion

# ── ComfyUI (Phase 3 可选) ──
COMFYUI_URL=http://127.0.0.1:8188

# ── bpy 配置 ──
BLENDER_HEADLESS=true
RIGIFY_PRESETS_DIR=/data/resources/presets

# ── 性能调优 ──
UNLOAD_MODEL_AFTER_STAGE=true   # 时分复用
SDXL_BATCH_SIZE=1
TORCH_COMPILE=false             # Phase 3 启用
```

### AutoDL 部署脚本

```bash
#!/bin/bash
# deploy_autodl.sh — AutoDL RTX 3090 一键部署

set -e

# 1. 安装依赖
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install diffusers transformers accelerate safetensors
pip install bpy>=4.1.0

# 2. 下载模型
bash scripts/download_models.sh

# 3. 配置环境
export PROCESSOR_MODE=local
export CUDA_DEVICE=cuda:0
export LOCAL_DEV=false

# 4. 初始化数据库
alembic upgrade head

# 5. 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# 6. 启动 Celery Worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=1 &
CELERY_PID=$!

echo "ArtPlatform started!"
echo "Backend PID: $UVICORN_PID"
echo "Celery PID: $CELERY_PID"
echo "API: http://localhost:8000/docs"

wait
```

### Docker Compose (Phase 2 生产)

```yaml
# docker-compose.yml
version: "3.8"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://artplatform:secret@db:5432/artplatform
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - PROCESSOR_MODE=local
      - CUDA_DEVICE=cuda:0
    depends_on:
      - db
      - redis
      - minio

  gpu-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.gpu
    environment:
      - DATABASE_URL=postgresql+asyncpg://artplatform:secret@db:5432/artplatform
      - REDIS_URL=redis://redis:6379/0
      - PROCESSOR_MODE=local
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - redis
      - db

  cpu-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://artplatform:secret@db:5432/artplatform
      - REDIS_URL=redis://redis:6379/0
      - PROCESSOR_MODE=local
      - CELERY_QUEUES=cpu
    depends_on:
      - redis
      - db

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - api

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: artplatform
      POSTGRES_USER: artplatform
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: artplatform
      MINIO_ROOT_PASSWORD: secret123456
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  miniodata:
```

### Dockerfile.gpu (GPU Worker)

```dockerfile
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# 安装 Python 3.11
RUN apt-get update && \
    apt-get install -y python3.11 python3.11-venv python3-pip && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

# 安装 Blender 依赖 (bpy 需要)
RUN apt-get install -y libxrender1 libxxf86vm1 libxxf86vm1 libxi6 libxfixes3

WORKDIR /app

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 && \
    pip install diffusers transformers accelerate safetensors && \
    pip install bpy>=4.1.0

COPY . .

# 预下载模型 (构建时下载，避免运行时等待)
RUN python scripts/download_models.py

# 启动 Celery Worker
CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
```

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| TripoSR 输出质量不稳定 | 网格粗糙，后续阶段困难 | 准备 Stable Fast 3D 备选；增加用户选图交互 |
| HY-Motion 24GB VRAM 需求 | 单 GPU 无法与其他模型共存 | 时分复用；或使用 Mixamo 预设降级 |
| Rigify 仅限人形 | 非人形角色无法绑定 | 集成 UniRig 作为备选处理器 |
| xatlas 编译困难 | 部署失败 | 使用 bpy Smart UV Project 替代 |
| bpy 版本兼容性 | pip bpy 可能与系统 Blender 冲突 | Docker 隔离；或只用 pip bpy 不装 Blender |
| 云 API 服务不稳定 | 管线中断 | 实现多服务商 fallback 链 |
| 模型下载慢 (国内) | 部署耗时长 | 使用 HF Mirror (`hf-mirror.com`) |

---

## 下一步行动

1. **立即**：将 Phase 1 云端 API 处理器实现为代码文件
2. **本周**：端到端测试 Phase 1 云 API 管线
3. **下周**：在 AutoDL 上搭建 Phase 2 自托管环境
4. **持续**：收集生成质量数据，优化参数和模型选择
