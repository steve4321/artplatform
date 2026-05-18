"""Cloud image-to-3D via ProviderRouter — Tripo Cloud / Meshy AI / CSM AI."""

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
class ImageTo3DCloudProcessor(PipelineProcessor):
    """Image-to-3D via ProviderRouter — primary + fallbacks from env vars.

    Env vars:
        IMAGE_TO_3D_PROVIDER=tripo_cloud
        IMAGE_TO_3D_FALLBACKS=meshy_ai,csm_ai

    Note: cloud providers typically require an image URL (not file path).
    The processor handles uploading the input image to a temp URL if needed.
    """

    stage = "image_to_3d"
    name = "image_to_3d_cloud"
    requires_gpu = False
    estimated_duration_s = 30

    def __init__(self):
        self._router = _build_router(
            "IMAGE_TO_3D_PROVIDER",
            "IMAGE_TO_3D_FALLBACKS",
        )

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        has_image = any(
            a.get("file_format") in ("png", "jpg", "jpeg", "webp")
            for a in input_artifacts
        )
        return has_image and self._router is not None

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        if self._router is None:
            raise RuntimeError(
                "No IMAGE_TO_3D_PROVIDER configured. "
                "Set IMAGE_TO_3D_PROVIDER env var."
            )

        image_artifact = next(
            (
                a
                for a in input_artifacts
                if a.get("file_format") in ("png", "jpg", "jpeg", "webp")
            ),
            None,
        )
        if not image_artifact:
            raise ValueError("No image artifact found for image_to_3d")

        local_path = image_artifact.get("_local_path") or image_artifact.get("local_path")
        if not local_path or not os.path.isfile(local_path):
            raise FileNotFoundError(f"Input image not found: {local_path}")

        # Upload image to a temp URL for providers that require URLs
        image_url = self._upload_for_provider(local_path)
        style = config.get("art_style", "realistic")

        params = GenerationParams(
            prompt=config.get("prompt", ""),
            extra={
                "image_url": image_url,
                "style": style,
                "image_path": local_path,
            },
        )

        assets = self._router.generate(Stage.IMAGE_TO_3D, params, output_dir)

        return [
            {
                "local_path": a.local_path,
                "file_format": a.file_format,
                "content_type": a.content_type,
                "metadata": a.metadata,
            }
            for a in assets
        ]

    def _upload_for_provider(self, local_path: str) -> str | None:
        """Upload image to a temporary URL for providers that need URLs.

        Returns the URL. Returns None if the primary provider supports file upload.
        """
        if self._router is None:
            return None

        # Check if primary supports file upload (self-hosted typically does)
        try:
            from app.ai.router import get_provider

            primary = get_provider(self._router.primary)
            # Self-hosted providers support file paths
            if "self_hosted" in primary.name:
                return None
        except Exception:
            pass

        # Upload to tmpfiles.org or similar for cloud API providers
        try:
            import uuid

            with open(local_path, "rb") as f:
                data = f.read()

            import httpx

            files = {"file": (f"{uuid.uuid4().hex}.png", data, "image/png")}
            resp = httpx.post(
                "https://tmpfiles.org/api/v1/upload",
                files=files,
                timeout=30,
            )
            if resp.status_code == 200:
                import json
                url = json.loads(resp.text).get("data", {}).get("url", "")
                # tmpfiles.org returns a redirect page URL; extract the direct link
                return url.replace("tmpfiles.org/", "tmpfiles.org/dl/") if url else None
        except Exception:
            pass

        return None
