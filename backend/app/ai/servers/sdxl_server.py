"""Self-hosted SDXL inference server — load model on demand, serve via HTTP."""

from __future__ import annotations

import logging
import os
import time
from base64 import b64decode, b64encode
from io import BytesIO
from typing import Any

import torch
from diffusers import StableDiffusionXLPipeline
from fastapi import FastAPI
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SDXL Inference Server")

_pipe = None
_device: str | None = None
_load_time: float | None = None


def _get_device() -> str:
    global _device
    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("SDXL device: %s", _device)
    return _device


def _load_pipeline() -> StableDiffusionXLPipeline:
    global _pipe, _load_time
    if _pipe is not None:
        return _pipe

    model_id = os.environ.get("SDXL_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0")
    device = _get_device()
    t0 = time.monotonic()

    logger.info("Loading SDXL model %s on %s …", model_id, device)
    dtype = torch.float16 if device == "cuda" else torch.float32
    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None,
    )
    pipe = pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    if device == "cuda":
        try:
            pipe.enable_vae_slicing()
            pipe.enable_attention_slicing()
        except Exception:
            pass

    _load_time = time.monotonic() - t0
    logger.info("SDXL loaded in %.1fs", _load_time)
    _pipe = pipe
    return _pipe


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": _pipe is not None}


@app.get("/stats")
async def stats():
    return {"model_loaded": _pipe is not None, "device": _get_device(), "load_time_s": _load_time}


@app.post("/generate")
async def generate(body: dict[str, Any]):
    pipe = _load_pipeline()
    device = _get_device()

    prompt = body.get("prompt", "")
    negative_prompt = body.get("negative_prompt", "")
    num_images = min(max(int(body.get("num_images", 1)), 1), 8)
    width = min(max(int(body.get("width", 1024)), 512), 2048)
    height = min(max(int(body.get("height", 1024)), 512), 2048)
    seed = body.get("seed")
    steps = min(max(int(body.get("steps", 30)), 1), 150)
    guidance_scale = float(body.get("guidance_scale", 7.5))
    width = (width // 8) * 8
    height = (height // 8) * 8

    generator = None
    if seed is not None:
        generator = torch.Generator(device=device).manual_seed(int(seed))

    logger.info(
        "Generating %d | %dx%d | steps=%d | cfg=%.1f | seed=%s",
        num_images, width, height, steps, guidance_scale, seed,
    )

    with torch.no_grad():
        result = pipe(
            prompt=[prompt] * num_images,
            negative_prompt=[negative_prompt] * num_images if negative_prompt else None,
            guidance_scale=guidance_scale,
            num_inference_steps=steps,
            width=width,
            height=height,
            generator=generator,
        )

    images = []
    for idx, image in enumerate(result.images):
        buf = BytesIO()
        image.save(buf, format="PNG")
        images.append({
            "index": idx,
            "base64": b64encode(buf.getvalue()).decode("utf-8"),
            "seed": int(generator.seed) + idx if seed is not None else None,
        })

    logger.info("Generated %d images for prompt='%s…'", len(images), prompt[:50])
    return {"images": images, "count": len(images), "prompt": prompt, "width": width, "height": height}


@app.post("/unload")
async def unload():
    global _pipe
    if _pipe is not None:
        del _pipe
        _pipe = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("SDXL unloaded from GPU")
    return {"status": "unloaded"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
