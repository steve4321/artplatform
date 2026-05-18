"""Meshy AI — image-to-3D cloud API with multiple art styles."""

from __future__ import annotations

import logging
import os
import time

import httpx

from app.ai.base import (
    GeneratedAsset,
    GenerationParams,
    ModelProvider,
    ProviderConfig,
    ProviderError,
    ProviderTimeout,
    Stage,
)

logger = logging.getLogger(__name__)


class MeshyAIProvider(ModelProvider):
    """Meshy AI cloud API — image to 3D with multiple art styles.

    API docs: https://docs.meshy.ai
    Pricing: ~$0.05/次 (credit-based)
    Art styles: realistic, anime, sculpt, etc.

    Note: Requires image_url in params.extra["image_url"].

    Env vars:
        MESHY_API_KEY
        MESHY_TIMEOUT — (optional) timeout in seconds
    """

    name = "meshy_ai"
    supports = [Stage.IMAGE_TO_3D]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.api_base = "https://api.meshy.ai/v1"
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    @classmethod
    def from_env(cls) -> "MeshyAIProvider":
        import os

        return cls(
            ProviderConfig(
                api_key=os.environ.get("MESHY_API_KEY", ""),
                timeout=int(os.environ.get("MESHY_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        if not self.config.api_key:
            return False
        try:
            resp = self.client.get(
                f"{self.api_base}/me",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # $0.05 per generation
        return 0.05

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        image_url = params.extra.get("image_url")
        style = params.extra.get("style", "realistic")

        if not image_url:
            raise ProviderError(
                "Meshy AI requires image_url in params.extra.image_url"
            )

        # Submit task
        resp = self.client.post(
            f"{self.api_base}/image-to-3d",
            json={
                "image_url": image_url,
                "art_style": style,
                "target_style": "none",
                "thumbnail_generation": True,
            },
        )

        if resp.status_code == 429:
            raise ProviderTimeout("Meshy AI rate limited")

        resp.raise_for_status()
        task_data = resp.json()
        task_id = task_data["id"]

        # Poll
        for _ in range(self.config.timeout // 5):
            time.sleep(5)
            status_resp = self.client.get(
                f"{self.api_base}/image-to-3d/{task_id}"
            )
            status_resp.raise_for_status()
            status = status_resp.json()

            if status["status"] == "completed":
                break
            elif status["status"] == "failed":
                raise ProviderError(
                    f"Meshy task failed: {status.get('error')}"
                )

        else:
            raise ProviderTimeout("Meshy AI task timed out")

        # Download GLB
        model_url = status["model_url"]
        path = os.path.join(output_dir, "model.glb")
        httpx.download_file(model_url, path)

        logger.info("Meshy AI generated 3D model: %s", path)
        return [
            GeneratedAsset(
                local_path=path,
                file_format="glb",
                content_type="model/gltf-binary",
                metadata={
                    "provider": self.name,
                    "task_id": task_id,
                    "style": style,
                },
            )
        ]
