"""Volcengine (火山引擎) Ark API — text-to-image via Seedream models."""

from __future__ import annotations

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

_DEFAULT_MODEL = "doubao-seedream-4-0-250828"
_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_SIZE_MAP = {
    (1024, 1024): "1024x1024",
    (1024, 1792): "1024x1792",
    (1792, 1024): "1792x1024",
    (512, 512): "512x512",
    (768, 768): "768x768",
}


class VolcengineProvider(ModelProvider):
    """Volcengine Ark API — Seedream text-to-image.

    API docs: https://www.volcengine.com/docs/6791/214588
    Model IDs: doubao-seedream-4-0-250828, doubao-seedream-4-5-251128, doubao-seedream-5-0-260128

    Env vars:
        ARK_API_KEY — API key from Volcengine Ark console
        VOLCENGINE_BASE_URL — (optional) override API base URL
        VOLCENGINE_MODEL — (optional) override default model
    """

    name = "volcengine"
    supports = [Stage.TEXT_TO_IMAGE]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.base_url = self.config.base_url or _DEFAULT_BASE_URL
        self.model = self.config.default_model or os.environ.get("VOLCENGINE_MODEL", _DEFAULT_MODEL)
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.config.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
            )
        return self._client

    @classmethod
    def from_env(cls) -> "VolcengineProvider":
        return cls(
            ProviderConfig(
                api_key=os.environ.get("ARK_API_KEY", ""),
                base_url=os.environ.get("VOLCENGINE_BASE_URL"),
                timeout=int(os.environ.get("VOLCENGINE_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        return bool(self.config.api_key)

    def estimate_cost(self, params: GenerationParams) -> float:
        return 0.01 * params.num_images

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        model = params.model_id or self.model
        size = _SIZE_MAP.get((params.width, params.height), f"{params.width}x{params.height}")

        payload: dict = {
            "model": model,
            "prompt": params.prompt,
            "size": size,
            "response_format": "url",
            "watermark": False,
        }

        if params.negative_prompt:
            payload["negative_prompt"] = params.negative_prompt
        if params.seed is not None:
            payload["seed"] = params.seed

        try:
            response = self.client.post(
                f"{self.base_url}/images/generations",
                json=payload,
            )

            if response.status_code == 429:
                raise ProviderTimeout("Volcengine rate limit exceeded")

            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise ProviderError(
                f"Volcengine API error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.TimeoutException:
            raise ProviderTimeout("Volcengine request timed out")

        data = response.json()
        artifacts = []

        for i, item in enumerate(data.get("data", [])):
            image_url = item.get("url", "")
            if not image_url:
                continue

            download_resp = httpx.get(image_url, timeout=60)
            download_resp.raise_for_status()

            path = os.path.join(output_dir, f"concept_{i}.png")
            with open(path, "wb") as f:
                f.write(download_resp.content)

            artifacts.append(
                GeneratedAsset(
                    local_path=path,
                    file_format="png",
                    content_type="image/png",
                    metadata={
                        "provider": self.name,
                        "model": model,
                        "prompt": params.prompt,
                    },
                )
            )

        logger.info("Volcengine generated %d images via %s", len(artifacts), model)
        return artifacts
