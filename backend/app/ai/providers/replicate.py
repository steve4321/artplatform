"""Replicate — multi-model cloud inference platform."""

from __future__ import annotations

import base64
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


class ReplicateProvider(ModelProvider):
    """Replicate cloud API — supports many open-source models.

    API docs: https://replicate.com/docs
    Pricing: per-second, varies by model

    Common SDXL models:
    - stability-ai/sdxl:dee63b7e8d7...  (official)
    - warmaid/sdxl:abcd... (optimized)

    Env vars:
        REPLICATE_API_KEY
        REPLICATE_TIMEOUT — (optional) timeout in seconds
    """

    name = "replicate"
    supports = [Stage.TEXT_TO_IMAGE, Stage.IMAGE_TO_3D]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.api_base = "https://api.replicate.com"
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
    def from_env(cls) -> "ReplicateProvider":
        import os

        return cls(
            ProviderConfig(
                api_key=os.environ.get("REPLICATE_API_KEY", ""),
                timeout=int(os.environ.get("REPLICATE_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        if not self.config.api_key:
            return False
        try:
            resp = self.client.get(f"{self.api_base}/v1/trainings", timeout=5)
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # Replicate charges per second; SDXL ~$0.001-0.005 per image
        return 0.003 * params.num_images

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        # Default SDXL model on Replicate
        model = params.model_id or "stability-ai/sdxl:abc123..."

        # Create prediction
        resp = self.client.post(
            f"{self.api_base}/v1/predictions",
            json={
                "version": model,
                "input": {
                    "prompt": params.prompt,
                    "negative_prompt": params.negative_prompt,
                    "num_inference_steps": params.steps,
                    "guidance_scale": params.guidance_scale,
                    "num_images": params.num_images,
                },
            },
        )

        if resp.status_code == 429:
            raise ProviderTimeout("Replicate rate limited")

        resp.raise_for_status()
        prediction = resp.json()
        prediction_url = prediction["urls"]["get"]

        # Poll until completed
        for _ in range(self.config.timeout // 2):
            time.sleep(2)
            status_resp = self.client.get(prediction_url)
            status_resp.raise_for_status()
            status_data = status_resp.json()

            if status_data["status"] == "succeeded":
                break
            elif status_data["status"] == "failed":
                raise ProviderError(
                    f"Replicate prediction failed: {status_data.get('error')}"
                )

        else:
            raise ProviderTimeout("Replicate prediction timed out")

        # Collect output
        output = status_data.get("output", [])
        if isinstance(output, dict):
            output = [output]

        artifacts = []
        for i, item in enumerate(output):
            if isinstance(item, str) and item.startswith("http"):
                path = os.path.join(output_dir, f"concept_{i}.png")
                httpx.download_file(item, path)
            else:
                path = os.path.join(output_dir, f"concept_{i}.png")
                with open(path, "wb") as f:
                    f.write(base64.b64decode(item))

            artifacts.append(
                GeneratedAsset(
                    local_path=path,
                    file_format="png",
                    content_type="image/png",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "prediction_id": prediction.get("id"),
                        "prompt": params.prompt,
                    },
                )
            )

        logger.info("Replicate generated %d images", len(artifacts))
        return artifacts
