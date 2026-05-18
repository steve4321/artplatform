"""fal.ai — low-latency text-to-image via WebSocket streaming."""

from __future__ import annotations

import logging
import os

import fal_client
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


class FalAIProvider(ModelProvider):
    """fal.ai cloud API — fast SDXL via WebSocket.

    API docs: https://fal.ai/docs
    Installation: pip install fal-client
    Pricing: ~$0.005/image

    fal.ai has two modes:
    1. sync — waits for completion (simpler, used here)
    2. subscribe — WebSocket streaming (lower latency)

    Env vars:
        FAL_API_KEY — fal.ai API key
        FAL_TIMEOUT — (optional) timeout in seconds
    """

    name = "fal_ai"
    supports = [Stage.TEXT_TO_IMAGE]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self._client: httpx.Client | None = None

    @classmethod
    def from_env(cls) -> "FalAIProvider":
        import os

        return cls(
            ProviderConfig(
                api_key=os.environ.get("FAL_API_KEY", ""),
                timeout=int(os.environ.get("FAL_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        if not self.config.api_key:
            return False
        try:
            fal_client.setenv(key=self.config.api_key)
            return True
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # fal.ai ~$0.005/image
        return 0.005 * params.num_images

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        fal_client.setenv(key=self.config.api_key)

        # fast-sdxl is quick; sdxl is higher quality
        model = params.model_id or "fal-ai/fast-sdxl"

        try:
            result = fal_client.subscribe(
                model,
                arguments={
                    "prompt": params.prompt,
                    "negative_prompt": params.negative_prompt,
                    "num_images": params.num_images,
                    "image_size": self._size_to_fal(params.width, params.height),
                },
                timeout=self.config.timeout,
            )
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise ProviderTimeout(f"fal.ai timed out: {exc}") from exc
            raise ProviderError(f"fal.ai error: {exc}") from exc

        artifacts = []
        for i, img_data in enumerate(result.get("images", [])):
            url = img_data["url"]
            seed = img_data.get("seed", 0)
            path = os.path.join(output_dir, f"concept_{i}_seed{seed}.png")

            httpx.download_file(url, path)

            artifacts.append(
                GeneratedAsset(
                    local_path=path,
                    file_format="png",
                    content_type="image/png",
                    metadata={
                        "provider": self.name,
                        "seed": seed,
                        "model": model,
                        "prompt": params.prompt,
                    },
                )
            )

        logger.info("fal.ai generated %d images", len(artifacts))
        return artifacts

    @staticmethod
    def _size_to_fal(w: int, h: int) -> str:
        """Convert dimensions to fal.ai size string."""
        if w == 1024 and h == 1024:
            return "square_hd"
        elif w == 768 and h == 768:
            return "square_1_1"
        elif w == 1536 and h == 1536:
            return "square_hd_30"
        elif w == 1024 and h == 576:
            return "landscape_4_3"
        elif w == 576 and h == 1024:
            return "portrait_3_4"
        else:
            return "square_hd"
