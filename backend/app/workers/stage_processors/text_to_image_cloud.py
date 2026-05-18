"""Cloud text-to-image via ProviderRouter — Stability AI / fal.ai / Replicate / ComfyUI."""

from __future__ import annotations

import logging
import os

from app.ai.base import GenerationParams, ProviderRouter, Stage
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)


def _build_router(primary_env: str, fallbacks_env: str) -> ProviderRouter | None:
    primary = os.environ.get(primary_env)
    fallback_str = os.environ.get(fallback_env, "")
    fallbacks = [f.strip() for f in fallback_str.split(",") if f.strip()] or []

    if not primary and not fallbacks:
        return None

    return ProviderRouter(
        primary=primary or fallbacks[0],
        fallbacks=fallbacks,
        cost_priority=os.environ.get("PROVIDER_COST_PRIORITY", "false").lower() == "true",
    )


@register
class SdxlCloudProcessor(PipelineProcessor):
    """Text-to-image via ProviderRouter — primary + fallbacks from env vars.

    Env vars control which providers are used:
        TEXT_TO_IMAGE_PROVIDER=stability_ai
        TEXT_TO_IMAGE_FALLBACKS=fal_ai,replicate
        PROVIDER_COST_PRIORITY=false

    The router handles all provider selection, fallback, and error recovery.
    """

    stage = "text_to_image"
    name = "sdxl_cloud"
    requires_gpu = False
    estimated_duration_s = 10

    def __init__(self):
        self._router = _build_router(
            "TEXT_TO_IMAGE_PROVIDER",
            "TEXT_TO_IMAGE_FALLBACKS",
        )

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt")) and self._router is not None

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        if self._router is None:
            raise RuntimeError(
                "No TEXT_TO_IMAGE_PROVIDER configured. "
                "Set TEXT_TO_IMAGE_PROVIDER env var."
            )

        params = GenerationParams(
            prompt=config["prompt"],
            negative_prompt=config.get("negative_prompt", ""),
            num_images=config.get("num_images", 2),
            width=config.get("width", 1024),
            height=config.get("height", 1024),
            seed=config.get("seed"),
            steps=config.get("steps", 30),
            guidance_scale=config.get("guidance_scale", 7.5),
            model_id=config.get("model_id"),
        )

        assets = self._router.generate(Stage.TEXT_TO_IMAGE, params, output_dir)

        return [
            {
                "local_path": a.local_path,
                "file_format": a.file_format,
                "content_type": a.content_type,
                "metadata": a.metadata,
            }
            for a in assets
        ]


@register
class SdxlComfyUIProcessor(PipelineProcessor):
    """Text-to-image via ComfyUI.

    Env vars:
        COMFYUI_URL=http://127.0.0.1:8188
        COMFYUI_WORKFLOW_TEXT_TO_IMAGE=<json or file path>
    """

    stage = "text_to_image"
    name = "sdxl_comfyui"
    requires_gpu = False
    estimated_duration_s = 15

    def __init__(self):
        self._router = _build_router("COMFYUI_PROVIDER", "COMFYUI_FALLBACKS")
        # Fall back to comfyui if no env configured
        if self._router is None and os.environ.get("COMFYUI_URL"):
            from app.ai.providers.comfyui import ComfyUIProvider
            from app.ai.router import register_provider

            provider = ComfyUIProvider.from_env()
            register_provider("comfyui", provider)
            self._router = ProviderRouter(primary="comfyui", fallbacks=[])

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(config.get("prompt")) and self._router is not None

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        if self._router is None:
            raise RuntimeError(
                "COMFYUI_URL not set. Cannot use sdxl_comfyui processor."
            )

        params = GenerationParams(
            prompt=config["prompt"],
            negative_prompt=config.get("negative_prompt", ""),
            num_images=config.get("num_images", 2),
            width=config.get("width", 1024),
            height=config.get("height", 1024),
            seed=config.get("seed"),
            steps=config.get("steps", 30),
            guidance_scale=config.get("guidance_scale", 7.5),
            model_id=config.get("model_id"),
        )

        assets = self._router.generate(Stage.TEXT_TO_IMAGE, params, output_dir)

        return [
            {
                "local_path": a.local_path,
                "file_format": a.file_format,
                "content_type": a.content_type,
                "metadata": a.metadata,
            }
            for a in assets
        ]
