"""Tripo 3D Cloud API — image-to-3D via TripoSR cloud."""

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


class TripoCloudProvider(ModelProvider):
    """Tripo 3D Cloud API — converts image to 3D mesh.

    API docs: https://api.tripo3d.ai/doc
    Pricing: ¥0.2-0.5 per generation
    Output: GLB with textures

    Note: This provider requires an image URL (not a file path).
    Upload the image first and pass the URL via params.extra["image_url"].

    Env vars:
        TRIPO_API_KEY
        TRIPO_TIMEOUT — (optional) timeout in seconds
    """

    name = "tripo_cloud"
    supports = [Stage.IMAGE_TO_3D]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.api_base = "https://api.tripo3d.ai/v2/openapi"
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.config.timeout,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
        return self._client

    @classmethod
    def from_env(cls) -> "TripoCloudProvider":
        import os

        return cls(
            ProviderConfig(
                api_key=os.environ.get("TRIPO_API_KEY", ""),
                timeout=int(os.environ.get("TRIPO_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        if not self.config.api_key:
            return False
        try:
            resp = self.client.get(
                f"{self.api_base}/user/info",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # ~¥0.3 per generation ≈ $0.04
        return 0.04

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        # Tripo Cloud requires the image URL (not file upload)
        image_url = params.extra.get("image_url")

        if not image_url:
            raise ProviderError(
                "Tripo Cloud requires image_url in params.extra.image_url. "
                "Upload the image first and pass the URL."
            )

        # Create task
        resp = self.client.post(
            f"{self.api_base}/task",
            json={
                "type": "image_to_model",
                "file": {"url": image_url},
                "config": {
                    "task_type": "image_to_model",
                    "model_format": "glb",
                    "texture_resolution": 1024,
                },
            },
        )

        if resp.status_code == 429:
            raise ProviderTimeout("Tripo Cloud rate limited")

        resp.raise_for_status()
        task_data = resp.json()
        task_id = task_data["data"]["task_id"]

        # Poll for completion
        for _ in range(self.config.timeout // 3):
            time.sleep(3)
            status_resp = self.client.get(
                f"{self.api_base}/task/{task_id}",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
            status_resp.raise_for_status()
            status = status_resp.json()["data"]

            if status["status"] == "success":
                break
            elif status["status"] == "failed":
                raise ProviderError(f"Tripo task failed: {status.get('error')}")

        else:
            raise ProviderTimeout("Tripo Cloud task timed out")

        # Download model
        model_url = status["output"]["model"]
        path = os.path.join(output_dir, "model.glb")
        httpx.download_file(model_url, path)

        artifacts = [
            GeneratedAsset(
                local_path=path,
                file_format="glb",
                content_type="model/gltf-binary",
                metadata={
                    "provider": self.name,
                    "task_id": task_id,
                    "model_url": model_url,
                },
            )
        ]

        # Download textures (if returned separately)
        if status["output"].get("textures"):
            for tex_name, tex_url in status["output"]["textures"].items():
                tex_path = os.path.join(output_dir, f"{tex_name}.png")
                httpx.download_file(tex_url, tex_path)
                artifacts.append(
                    GeneratedAsset(
                        local_path=tex_path,
                        file_format="png",
                        content_type="image/png",
                        metadata={
                            "provider": self.name,
                            "texture_type": tex_name,
                        },
                    )
                )

        logger.info("Tripo Cloud generated 3D model: %s", path)
        return artifacts
