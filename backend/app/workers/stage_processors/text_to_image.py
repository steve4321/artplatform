from __future__ import annotations

import logging
import os
import threading

import torch
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

# Module-level model cache – loaded once, reused across calls.
# Protected by a lock so that concurrent Celery workers don't race.
_pipeline = None
_pipeline_lock = threading.Lock()
_device: str | None = None


def _get_device() -> str:
    global _device
    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("SDXL device: %s", _device)
    return _device


def _load_pipeline(model_id: str):
    global _pipeline
    if _pipeline is not None:
        # If the requested model changed, discard the cached one.
        if getattr(_pipeline, "_cached_model_id", None) != model_id:
            logger.info("SDXL model changed (%s -> %s), reloading", _pipeline._cached_model_id, model_id)
            del _pipeline
            _pipeline = None
        else:
            return _pipeline

    from diffusers import StableDiffusionXLPipeline

    device = _get_device()
    logger.info("Loading SDXL model %s on %s …", model_id, device)

    dtype = torch.float16 if device == "cuda" else torch.float32
    pipe = StableDiffusionXLPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None,
    )
    pipe = pipe.to(device)

    # Keep model on GPU but disable progress bar in production.
    pipe.set_progress_bar_config(disable=True)

    if device == "cuda":
        try:
            pipe.enable_vae_slicing()
        except Exception:
            pass

    pipe._cached_model_id = model_id  # type: ignore[attr-defined]
    _pipeline = pipe
    return _pipeline


@register
class TextToImageSDXL(PipelineProcessor):
    stage = "text_to_image"
    name = "sdxl"
    requires_gpu = True
    estimated_duration_s = 10

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt"))

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        model_id: str = config.get("model_id", "stabilityai/stable-diffusion-xl-base-1.0")
        prompt: str = config["prompt"]
        negative_prompt: str | None = config.get("negative_prompt")
        guidance_scale: float = float(config.get("guidance_scale", 7.5))
        num_inference_steps: int = int(config.get("num_inference_steps", 30))
        width: int = int(config.get("width", 1024))
        height: int = int(config.get("height", 1024))
        seed: int | None = config.get("seed")
        num_images: int = int(config.get("num_images", 2))

        # Clamp values to sensible ranges.
        num_images = max(1, min(num_images, 8))
        num_inference_steps = max(1, min(num_inference_steps, 150))
        width = max(512, min(width, 2048))
        height = max(512, min(height, 2048))
        # Ensure multiples of 8 (required by SDXL VAE).
        width = (width // 8) * 8
        height = (height // 8) * 8

        with _pipeline_lock:
            pipe = _load_pipeline(model_id)

        generator = None
        if seed is not None:
            device = _get_device()
            generator = torch.Generator(device=device).manual_seed(seed)

        logger.info(
            "SDXL: generating %d image(s) | %dx%d | steps=%d | cfg=%.1f",
            num_images, width, height, num_inference_steps, guidance_scale,
        )

        with torch.no_grad():
            result = pipe(
                prompt=[prompt] * num_images,
                negative_prompt=[negative_prompt] * num_images if negative_prompt else None,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                width=width,
                height=height,
                generator=generator,
            )

        artifacts: list[dict] = []
        for idx, image in enumerate(result.images):
            filename = f"sdxl_{idx:03d}.png"
            filepath = os.path.join(output_dir, filename)
            image.save(filepath, "PNG")
            artifacts.append({
                "local_path": filepath,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "generator": "sdxl",
                    "model_id": model_id,
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "guidance_scale": guidance_scale,
                    "num_inference_steps": num_inference_steps,
                    "width": width,
                    "height": height,
                    "seed": seed,
                    "index": idx,
                },
            })

        logger.info("SDXL: saved %d image(s) to %s", len(artifacts), output_dir)
        return artifacts
