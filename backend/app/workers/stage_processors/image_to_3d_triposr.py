import logging
import os
import sys
import threading

import torch
import numpy as np
import mcubes
import trimesh

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

_MODEL = None
_MODEL_LOCK = threading.Lock()
_DEVICE: str | None = None

_TRIPOSR_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".local_libs", "TripoSR")
if os.path.isdir(_TRIPOSR_PATH) and _TRIPOSR_PATH not in sys.path:
    sys.path.insert(0, os.path.abspath(_TRIPOSR_PATH))

_TRIPOSR_LOCAL = "/tmp/triposr"
_DINO_LOCAL = "/tmp/facebook_dino-vitb16"


def _get_device() -> str:
    global _DEVICE
    if _DEVICE is None:
        _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("TripoSR device: %s", _DEVICE)
    return _DEVICE


def _patch_hf_and_mc():
    import huggingface_hub
    _orig = huggingface_hub.hf_hub_download

    def _patched(repo_id, filename=None, **kwargs):
        local_map = {
            ("facebook/dino-vitb16", "config.json"): f"{_DINO_LOCAL}/config.json",
            ("facebook/dino-vitb16", "pytorch_model.bin"): f"{_DINO_LOCAL}/pytorch_model.bin",
            ("stabilityai/TripoSR", "config.yaml"): f"{_TRIPOSR_LOCAL}/config.yaml",
            ("stabilityai/TripoSR", "model.ckpt"): f"{_TRIPOSR_LOCAL}/model.ckpt",
        }
        key = (repo_id, filename)
        if filename and key in local_map and os.path.exists(local_map[key]):
            return local_map[key]
        return _orig(repo_id, filename=filename, **kwargs)

    huggingface_hub.hf_hub_download = _patched

    def _mc_marching_cubes(volume, threshold):
        if isinstance(volume, torch.Tensor):
            volume_np = volume.detach().cpu().numpy()
        else:
            volume_np = np.asarray(volume)
        verts, triangles = mcubes.marching_cubes(volume_np, threshold)
        return torch.from_numpy(verts).float(), torch.from_numpy(triangles).long()

    sys.modules['torchmcubes'] = type(sys)('torchmcubes')
    sys.modules['torchmcubes'].marching_cubes = _mc_marching_cubes
    sys.modules['torchmcubes_module'] = sys.modules['torchmcubes']


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    _patch_hf_and_mc()

    from tsr.system import TSR

    logger.info("Loading TripoSR from local files…")
    model = TSR.from_pretrained(
        _TRIPOSR_LOCAL,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.renderer.set_chunk_size(8192)
    model.to(_get_device())
    model.eval()

    _MODEL = model
    return model


@register
class ImageTo3DTripoSR(PipelineProcessor):
    stage = "image_to_3d"
    name = "triposr"
    requires_gpu = False
    estimated_duration_s = 60

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("png", "jpg", "jpeg", "webp")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        from PIL import Image
        from tsr.utils import remove_background, resize_foreground

        image_artifact = next(
            a for a in input_artifacts
            if a.get("file_format") in ("png", "jpg", "jpeg", "webp")
        )
        local_path = image_artifact.get("_local_path") or image_artifact.get("local_path")
        if not local_path or not os.path.isfile(local_path):
            raise FileNotFoundError(f"Input image not found: {local_path}")

        pil_image = Image.open(local_path).convert("RGB")

        with _MODEL_LOCK:
            model = _load_model()

        device = _get_device()

        bg_threshold = float(config.get("background_threshold", 0.85))
        pil_image_no_bg = remove_background(pil_image, None)
        pil_image_no_bg = resize_foreground(pil_image_no_bg, bg_threshold)
        image_np = np.array(pil_image_no_bg).astype(np.float32) / 255.0
        image_np = image_np[:, :, :3] * image_np[:, :, 3:4] + (1 - image_np[:, :, 3:4]) * 0.5
        pil_image = Image.fromarray((image_np * 255.0).astype(np.uint8))

        logger.info("TripoSR: generating 3D from %s", os.path.basename(local_path))

        with torch.no_grad():
            scene_codes = model([pil_image], device=device)

        meshes = model.extract_mesh(scene_codes, has_vertex_color=True, resolution=256)
        mesh = meshes[0]

        output_path = os.path.join(output_dir, "triposr_output.glb")
        mesh.export(output_path, file_type="glb")

        logger.info(
            "TripoSR: saved GLB to %s (%d verts, %d faces)",
            output_path, len(mesh.vertices), len(mesh.faces)
        )

        return [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "generator": "triposr",
                "model_name": "stabilityai/TripoSR",
                "vertex_count": len(mesh.vertices),
                "face_count": len(mesh.faces),
            },
        }]
