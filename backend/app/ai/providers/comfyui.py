"""ComfyUI — visual pipeline editor as inference backend."""

from __future__ import annotations

import json
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


class ComfyUIProvider(ModelProvider):
    """ComfyUI as inference backend — supports any ComfyUI workflow.

    Deploy ComfyUI: python main.py --listen 0.0.0.0 --port 8188

    How it works:
    1. Load workflow JSON (from env var or built-in default)
    2. Inject prompt/params into workflow nodes
    3. Submit to ComfyUI /prompt endpoint
    4. Poll /history/{prompt_id} until done
    5. Download output images from /view

    Env vars:
        COMFYUI_URL — ComfyUI server URL, default: http://127.0.0.1:8188
        COMFYUI_WORKFLOW_{STAGE} — JSON string or file path for stage workflow
        COMFYUI_TIMEOUT — (optional) timeout in seconds
    """

    name = "comfyui"
    supports = [Stage.TEXT_TO_IMAGE]

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config)
        self.url = self.config.base_url or os.environ.get(
            "COMFYUI_URL", "http://127.0.0.1:8188"
        )
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.config.timeout)
        return self._client

    @classmethod
    def from_env(cls) -> "ComfyUIProvider":
        import os

        return cls(
            ProviderConfig(
                api_key="n/a",
                base_url=os.environ.get(
                    "COMFYUI_URL", "http://127.0.0.1:8188"
                ),
                timeout=int(os.environ.get("COMFYUI_TIMEOUT", "180")),
            )
        )

    def health_check(self) -> bool:
        try:
            resp = self.client.get(f"{self.url}/system_stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def estimate_cost(self, params: GenerationParams) -> float:
        # Self-hosted: only electricity
        return 0.0

    def _get_workflow(self, stage: Stage) -> dict:
        """Load workflow JSON for the given stage.

        Priority:
        1. Environment var COMFYUI_WORKFLOW_{STAGE} (JSON string or file path)
        2. Built-in default workflow
        """
        stage_name = stage.value.upper()
        workflow_env = f"COMFYUI_WORKFLOW_{stage_name}"
        workflow_json = os.environ.get(workflow_env)

        if workflow_json:
            if os.path.isfile(workflow_json):
                with open(workflow_json) as f:
                    return json.load(f)
            return json.loads(workflow_json)

        return self._default_sdxl_workflow()

    def _default_sdxl_workflow(self) -> dict:
        """Built-in SDXL text-to-image workflow.

        Node IDs (customize in your ComfyUI installation):
        - 4: CheckpointLoaderSimple (loads SDXL)
        - 6: CLIPTextEncode (positive prompt)
        - 7: CLIPTextEncode (negative prompt)
        - 5: EmptyLatentImage
        - 3: KSampler
        - 8: VAEDecode
        - 9: SaveImage
        """
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7.5,
                    "denoise": 1.0,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "seed": 42,
                    "steps": 30,
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "sdxl_base_1.0.safetensors"
                },
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": 1024, "width": 1024},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "PROMPT"},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["4", 1], "text": "NEGATIVE"},
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "artplatform",
                    "images": ["8", 0],
                },
            },
        }

    def _inject_params(self, workflow: dict, params: GenerationParams) -> dict:
        """Fill prompt and parameters into the workflow JSON."""
        workflow = json.loads(json.dumps(workflow))  # deep copy

        for node_id, node in workflow.items():
            class_type = node.get("class_type", "")

            if class_type == "CLIPTextEncode":
                inputs = node.get("inputs", {})
                text = inputs.get("text", "")
                if text == "PROMPT":
                    node["inputs"]["text"] = params.prompt
                elif text == "NEGATIVE":
                    node["inputs"]["text"] = params.negative_prompt

            elif class_type == "KSampler":
                node["inputs"]["steps"] = params.steps
                node["inputs"]["cfg"] = params.guidance_scale
                if params.seed is not None:
                    node["inputs"]["seed"] = params.seed

            elif class_type == "EmptyLatentImage":
                node["inputs"]["width"] = params.width
                node["inputs"]["height"] = params.height
                node["inputs"]["batch_size"] = params.num_images

        return workflow

    def _wait_for_completion(self, prompt_id: str, timeout: int) -> dict:
        t0 = time.time()
        while time.time() - t0 < timeout:
            resp = self.client.get(f"{self.url}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(1)
        raise ProviderTimeout(
            f"ComfyUI prompt {prompt_id} timed out after {timeout}s"
        )

    def generate(
        self, params: GenerationParams, output_dir: str
    ) -> list[GeneratedAsset]:
        workflow = self._get_workflow(Stage.TEXT_TO_IMAGE)
        workflow = self._inject_params(workflow, params)

        # Submit workflow
        resp = self.client.post(
            f"{self.url}/prompt", json={"prompt": workflow}
        )
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        # Wait for completion
        result = self._wait_for_completion(prompt_id, self.config.timeout)

        # Collect output images
        artifacts = []
        images_info = result.get("outputs", {}).get("9", {}).get(
            "images", []
        )
        for img_info in images_info:
            filename = img_info["filename"]
            subfolder = img_info.get("subfolder", "")

            img_resp = self.client.get(
                f"{self.url}/view",
                params={"filename": filename, "subfolder": subfolder},
            )
            img_resp.raise_for_status()

            path = os.path.join(output_dir, filename)
            with open(path, "wb") as f:
                f.write(img_resp.content)

            artifacts.append(
                GeneratedAsset(
                    local_path=path,
                    file_format="png",
                    content_type="image/png",
                    metadata={
                        "provider": self.name,
                        "prompt_id": prompt_id,
                        "filename": filename,
                    },
                )
            )

        logger.info("ComfyUI generated %d images", len(artifacts))
        return artifacts
