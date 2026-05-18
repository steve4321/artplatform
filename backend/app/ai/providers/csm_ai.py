"""CSM (Common Sense Machines) — image-to-3D with character support."""

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


class CSMAIProvider(ModelProvider):
    """CSM AI — image to 3D, supports characters and scene models.

    API docs: https://docs.csm.ai
    Pricing: ~$0.03/次

    Note: Requires image_url in params.extra["image_url"].

    Env vars:
        CSM_API_KEY
        CSM_TIMEOUT — (optional) timeout in seconds
    """

    name = "csm_ai"
    supports = [Stage.IMAGE_TO_3D]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.api_base = "https://api.csm.ai/v1"
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
    def from_env(cls) -> "CSMAIProvider":
        import os

        return cls(
            ProviderConfig(
                api_key=os.environ.get("CSM_API_KEY", ""),
                timeout=int(os.environ.get("CSM_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        if not self.config.api_key:
            return False
        try:
            resp = self.client.get(f"{self.api_base}/user", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        return 0.03

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        image_url = params.extra.get("image_url")

        if not image_url:
            raise ProviderError(
                "CSM AI requires image_url in params.extra.image_url"
            )

        resp = self.client.post(
            f"{self.api_base}/generate",
            json={
                "image_url": image_url,
                "mode": params.extra.get("mode", "standard"),
            },
        )

        if resp.status_code == 429:
            raise ProviderTimeout("CSM AI rate limited")

        resp.raise_for_status()
        task_data = resp.json()
        task_id = task_data["task_id"]

        for _ in range(self.config.timeout // 5):
            time.sleep(5)
            status_resp = self.client.get(
                f"{self.api_base}/task/{task_id}"
            )
            status_resp.raise_for_status()
            status = status_resp.json()

            if status["status"] == "completed":
                break
            elif status["status"] == "failed":
                raise ProviderError(
                    f"CSM task failed: {status.get('error')}"
                )

        else:
            raise ProviderTimeout("CSM AI task timed out")

        path = os.path.join(output_dir, "model.glb")
        httpx.download_file(status["result_url"], path)

        return [
            GeneratedAsset(
                local_path=path,
                file_format="glb",
                content_type="model/gltf-binary",
                metadata={
                    "provider": self.name,
                    "task_id": task_id,
                },
            )
        ]
