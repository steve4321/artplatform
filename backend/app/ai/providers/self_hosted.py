"""Self-hosted inference providers — diffusers + local GPU servers."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

from app.ai.base import (
    GeneratedAsset,
    GenerationParams,
    ModelProvider,
    ProviderConfig,
    ProviderError,
    Stage,
)

if TYPE_CHECKING:
    import torch
    from diffusers import StableDiffusionXLPipeline
    from tsr.models import TSR

logger = logging.getLogger(__name__)


class SelfHostedSDXLProvider(ModelProvider):
    """Self-hosted SDXL via diffusers — on-premises GPU inference.

    Two modes:
    1. HTTP server mode: hits an external inference server (recommended)
       Deploy: python -m app.ai.servers.sdxl_server
    2. Inline mode: loads model directly in worker process (needs VRAM)

    HTTP server mode is recommended to avoid loading torch at startup.

    Env vars:
        SELF_HOSTED_SDXL=true
        SELF_HOSTED_SDXL_URL — HTTP server URL (e.g. http://localhost:8001)
        SDXL_MODEL_ID — HuggingFace model ID
        CUDA_DEVICE — (optional) CUDA device, default: cuda
        UNLOAD_MODEL_AFTER_STAGE — (optional) unload after inference, default: true
    """

    name = "self_hosted_sdxl"
    supports = [Stage.TEXT_TO_IMAGE]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.server_url = self.config.base_url or os.environ.get(
            "SELF_HOSTED_SDXL_URL", "http://localhost:8001"
        )
        self.model_id = self.config.default_model or os.environ.get(
            "SDXL_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0"
        )
        self.device = os.environ.get("CUDA_DEVICE", "cuda")
        self._pipe: "StableDiffusionXLPipeline | None" = None
        self._use_http = bool(self.server_url)

    @classmethod
    def from_env(cls) -> "SelfHostedSDXLProvider":
        import os

        return cls(
            ProviderConfig(
                api_key="n/a",
                base_url=os.environ.get("SELF_HOSTED_SDXL_URL"),
                default_model=os.environ.get(
                    "SDXL_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0"
                ),
                timeout=int(os.environ.get("SELF_HOSTED_TIMEOUT", "120")),
            )
        )

    def health_check(self) -> bool:
        if self._use_http:
            try:
                resp = httpx.get(f"{self.server_url}/health", timeout=5)
                return resp.status_code == 200
            except Exception:
                return False
        # Inline mode: check CUDA availability
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # Self-hosted: only electricity cost, no API fees
        return 0.0

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        if self._use_http:
            return self._generate_http(params, output_dir)
        return self._generate_inline(params, output_dir)

    def _generate_http(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        import base64
        import uuid

        resp = httpx.post(
            f"{self.server_url}/generate",
            json={
                "prompt": params.prompt,
                "negative_prompt": params.negative_prompt,
                "num_images": params.num_images,
                "width": params.width,
                "height": params.height,
                "seed": params.seed,
                "steps": params.steps,
                "guidance_scale": params.guidance_scale,
            },
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        artifacts = []
        for i, img_data in enumerate(data.get("images", [])):
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
                        "model_id": self.model_id,
                    },
                )
            )

        return artifacts

    def _generate_inline(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        import torch
        from diffusers import StableDiffusionXLPipeline

        if self._pipe is None:
            self._pipe = StableDiffusionXLPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16,
                variant="fp16",
            )
            self._pipe = self._pipe.to(self.device)
            self._pipe.enable_vae_slicing()

        generator = None
        if params.seed is not None:
            generator = torch.Generator(self.device).manual_seed(
                params.seed
            )

        results = self._pipe(
            prompt=params.prompt,
            negative_prompt=params.negative_prompt,
            num_images_per_prompt=params.num_images,
            width=params.width,
            height=params.height,
            generator=generator,
            num_inference_steps=params.steps,
            guidance_scale=params.guidance_scale,
        )

        artifacts = []
        for i, image in enumerate(results.images):
            path = os.path.join(output_dir, f"concept_{i}.png")
            image.save(path, "PNG")
            artifacts.append(
                GeneratedAsset(
                    local_path=path,
                    file_format="png",
                    content_type="image/png",
                    metadata={
                        "provider": self.name,
                        "model_id": self.model_id,
                    },
                )
            )

        # Unload to free VRAM for next stage
        if os.environ.get("UNLOAD_MODEL_AFTER_STAGE", "true").lower() == "true":
            del self._pipe
            self._pipe = None
            torch.cuda.empty_cache()

        return artifacts


class SelfHostedTripoSRProvider(ModelProvider):
    """Self-hosted TripoSR via tsr library.

    Two modes:
    1. HTTP server mode: hits external inference server
       Deploy: python -m app.ai.servers.triposr_server
    2. Inline mode: loads model directly in worker process

    Requires image_path in params.extra["image_path"].

    Env vars:
        SELF_HOSTED_TRIPOSR=true
        SELF_HOSTED_TRIPOSR_URL — HTTP server URL
        TRIPOSR_MODEL_PATH — local model path
    """

    name = "self_hosted_triposr"
    supports = [Stage.IMAGE_TO_3D]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.server_url = self.config.base_url or os.environ.get(
            "SELF_HOSTED_TRIPOSR_URL"
        )
        self.model_path = self.config.default_model or os.environ.get(
            "TRIPOSR_MODEL_PATH"
        )
        self._model: "TSR | None" = None
        self._use_http = bool(self.server_url)

    @classmethod
    def from_env(cls) -> "SelfHostedTripoSRProvider":
        import os

        return cls(
            ProviderConfig(
                api_key="n/a",
                base_url=os.environ.get("SELF_HOSTED_TRIPOSR_URL"),
                default_model=os.environ.get("TRIPOSR_MODEL_PATH"),
                timeout=int(os.environ.get("TRIPOSR_TIMEOUT", "60")),
            )
        )

    def health_check(self) -> bool:
        if self._use_http:
            try:
                resp = httpx.get(f"{self.server_url}/health", timeout=5)
                return resp.status_code == 200
            except Exception:
                return False
        return True

    def estimate_cost(self, params: GenerationParams) -> float:
        return 0.0

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        if self._use_http:
            return self._generate_http(params, output_dir)
        return self._generate_inline(params, output_dir)

    def _generate_http(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        image_url = params.extra.get("image_url")
        image_path = params.extra.get("image_path")

        if image_url:
            resp = httpx.post(
                f"{self.server_url}/generate",
                json={"image_url": image_url},
                timeout=self.config.timeout,
            )
        elif image_path:
            with open(image_path, "rb") as f:
                resp = httpx.post(
                    f"{self.server_url}/generate",
                    files={"file": f},
                    timeout=self.config.timeout,
                )
        else:
            raise ProviderError(
                "Need image_url or image_path in params.extra"
            )

        resp.raise_for_status()
        data = resp.json()

        path = os.path.join(output_dir, "model.glb")
        httpx.download_file(data["model_url"], path)

        return [
            GeneratedAsset(
                local_path=path,
                file_format="glb",
                content_type="model/gltf-binary",
                metadata={
                    "provider": self.name,
                    "model_source": data.get("source", "triposr"),
                },
            )
        ]

    def _generate_inline(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        import torch
        from PIL import Image
        from tsr.models import TSR
        from tsr.utils import remove_background

        if self._model is None:
            self._model = TSR.from_pretrained(
                self.model_path or "stabilityai/TripoSR",
                config_name="config.json",
                weight_name="model.ckpt",
            )
            self._model.renderer.settings.chunk_size = 8192
            self._model.to("cuda")

        image_path = params.extra.get("image_path")
        if not image_path:
            raise ProviderError("Need image_path in params.extra")

        image = Image.open(image_path).convert("RGBA")
        if params.extra.get("remove_background", True):
            image = remove_background(image)

        with torch.no_grad():
            scenes = self._model([image], device="cuda")

        mesh = scenes[0][0]
        path = os.path.join(output_dir, "model.glb")
        mesh.export(path)

        return [
            GeneratedAsset(
                local_path=path,
                file_format="glb",
                content_type="model/gltf-binary",
                metadata={
                    "provider": self.name,
                    "vertex_count": len(mesh.vertices),
                    "face_count": len(mesh.faces),
                },
            )
        ]
