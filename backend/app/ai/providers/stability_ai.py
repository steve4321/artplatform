"""Stability AI cloud API — text-to-image via SDXL."""

from __future__ import annotations

import base64
import logging
import os

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


class StabilityAIProvider(ModelProvider):
    """Stability AI official API — SDXL text-to-image.

    API docs: https://platform.stability.ai/docs/api-reference
    Pricing: $0.003/image for SDXL

    Env vars:
        STABILITY_API_KEY — API key from Stability AI dashboard
        STABILITY_BASE_URL — (optional) override API base URL
        STABILITY_TIMEOUT — (optional) request timeout in seconds
    """

    name = "stability_ai"
    supports = [Stage.TEXT_TO_IMAGE]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.base_url = self.config.base_url or "https://api.stability.ai/v1"
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
    def from_env(cls) -> "StabilityAIProvider":
        import os

        return cls(
            ProviderConfig(
                api_key=os.environ.get("STABILITY_API_KEY", ""),
                base_url=os.environ.get("STABILITY_BASE_URL"),
                timeout=int(os.environ.get("STABILITY_TIMEOUT", "60")),
            )
        )

    def health_check(self) -> bool:
        if not self.config.api_key:
            return False
        try:
            resp = self.client.get(
                "https://api.stability.ai/v1/user/balance",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # $0.003 per image for SDXL
        return 0.003 * params.num_images

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        engine = params.model_id or "stable-diffusion-xl-1024-v1-0"

        try:
            response = self.client.post(
                f"{self.base_url}/generation/{engine}/text-to-image",
                json={
                    "text_prompts": [
                        {"text": params.prompt, "weight": 1.0},
                        *(
                            [{"text": params.negative_prompt, "weight": -1.0}]
                            if params.negative_prompt
                            else []
                        ),
                    ],
                    "cfg_scale": params.guidance_scale,
                    "steps": params.steps,
                    "width": params.width,
                    "height": params.height,
                    "samples": params.num_images,
                },
            )

            if response.status_code == 429:
                raise ProviderTimeout("Stability AI rate limit exceeded")

            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Stability AI API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.TimeoutException:
            raise ProviderTimeout("Stability AI request timed out")

        data = response.json()
        artifacts = []

        for i, img_data in enumerate(data.get("artifacts", [])):
            seed = img_data.get("seed", 0)
            path = os.path.join(output_dir, f"concept_{i}_seed{seed}.png")

            with open(path, "wb") as f:
                f.write(base64.b64decode(img_data["base64"]))

            artifacts.append(
                GeneratedAsset(
                    local_path=path,
                    file_format="png",
                    content_type="image/png",
                    metadata={
                        "provider": self.name,
                        "seed": seed,
                        "engine": engine,
                        "prompt": params.prompt,
                    },
                )
            )

        logger.info("StabilityAI generated %d images", len(artifacts))
        return artifacts
