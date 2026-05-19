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

_OPENLRM_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".local_libs", "OpenLRM")
if os.path.isdir(_OPENLRM_PATH) and _OPENLRM_PATH not in sys.path:
    sys.path.insert(0, os.path.abspath(_OPENLRM_PATH))


def _get_device() -> str:
    global _DEVICE
    if _DEVICE is None:
        _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("OpenLRM device: %s", _DEVICE)
    return _DEVICE


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    from openlrm.models import model_dict
    from openlrm.utils.hf_hub import wrap_model_hub

    model_name = "zxhezexin/openlrm-obj-small-1.0"
    logger.info("Loading OpenLRM model %s …", model_name)

    hf_model_cls = wrap_model_hub(model_dict["lrm"])
    model = hf_model_cls.from_pretrained(model_name)
    model = model.to(_get_device())
    model.eval()

    _MODEL = model
    return model


def _infer_planes(model, image_tensor: torch.Tensor, source_cam_dist: float = 2.0):
    from openlrm.datasets.cam_utils import build_camera_principle, create_intrinsics

    device = _get_device()
    N = image_tensor.shape[0]
    canonical_extrinsics = torch.tensor([[
        [1, 0, 0, 0],
        [0, 0, -1, -source_cam_dist],
        [0, 1, 0, 0],
    ]], dtype=torch.float32, device=device)
    intrinsics = create_intrinsics(f=0.75, c=0.5, device=device).unsqueeze(0)
    source_camera = build_camera_principle(canonical_extrinsics, intrinsics)
    planes = model.forward_planes(image_tensor, source_camera.repeat(N, 1))
    return planes


def _extract_mesh(model, planes: torch.Tensor, mesh_size: int = 256, mesh_thres: float = 3.0) -> trimesh.Trimesh:
    grid_out = model.synthesizer.forward_grid(planes=planes, grid_size=mesh_size)
    sigma = grid_out["sigma"].squeeze(0).squeeze(-1).cpu().numpy()

    vtx, faces = mcubes.marching_cubes(sigma, mesh_thres)
    vtx = vtx / (mesh_size - 1) * 2 - 1

    vtx_tensor = torch.tensor(vtx, dtype=torch.float32, device=_get_device()).unsqueeze(0)
    vtx_colors = model.synthesizer.forward_points(planes, vtx_tensor)["rgb"].squeeze(0).cpu().numpy()
    vtx_colors = (vtx_colors * 255).astype(np.uint8)

    return trimesh.Trimesh(vertices=vtx, faces=faces, vertex_colors=vtx_colors)


@register
class ImageTo3DOpenLRM(PipelineProcessor):
    stage = "image_to_3d"
    name = "openlrm"
    requires_gpu = True
    estimated_duration_s = 30

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("png", "jpg", "jpeg", "webp")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        from PIL import Image

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

        source_size = 224
        image_tensor = (
            torch.from_numpy(np.array(pil_image))
            .permute(2, 0, 1)
            .unsqueeze(0)
            .float()
            .to(_get_device())
            / 255.0
        )
        image_tensor = torch.nn.functional.interpolate(
            image_tensor, size=(source_size, source_size), mode="bicubic", align_corners=True
        )
        image_tensor = torch.clamp(image_tensor, 0, 1)

        logger.info("OpenLRM: generating 3D from %s", os.path.basename(local_path))
        planes = _infer_planes(model, image_tensor, source_cam_dist=2.0)

        mesh = _extract_mesh(model, planes, mesh_size=256, mesh_thres=3.0)

        output_path = os.path.join(output_dir, "openlrm_output.glb")
        mesh.export(output_path, file_type="glb")

        logger.info("OpenLRM: saved GLB to %s (%d verts, %d faces)", output_path, len(mesh.vertices), len(mesh.faces))

        return [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "generator": "openlrm",
                "model_name": "zxhezexin/openlrm-obj-small-1.0",
                "vertex_count": len(mesh.vertices),
                "face_count": len(mesh.faces),
            },
        }]
