from __future__ import annotations

import logging
import os
import threading

import torch
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_device: str | None = None


def _get_device() -> str:
    global _device
    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("TripoSR device: %s", _device)
    return _device


def _load_model(model_path: str = "stabilityai/TripoSR"):
    global _model
    if _model is not None:
        return _model

    device = _get_device()
    logger.info("Loading TripoSR model from %s on %s …", model_path, device)

    from tsr.models import TSR

    model = TSR.from_pretrained(
        model_path,
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    model.to(device)
    model.renderer.set_device(device)

    _model = model
    return _model


def _find_image_artifact(input_artifacts: list[dict]) -> dict | None:
    image_formats = {"png", "jpg", "jpeg", "webp"}
    for artifact in input_artifacts:
        if artifact.get("file_format") in image_formats:
            return artifact
    return None


@register
class ImageTo3DTripoSR(PipelineProcessor):
    stage = "image_to_3d"
    name = "triposr"
    requires_gpu = True
    estimated_duration_s = 30

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in ("png", "jpg", "jpeg", "webp")
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        model_path: str = config.get("model_path", "stabilityai/TripoSR")
        model_resolution: int = int(config.get("model_resolution", 256))
        chunk_size: int = int(config.get("chunk_size", 8192))

        image_artifact = _find_image_artifact(input_artifacts)
        if image_artifact is None:
            raise ValueError("No image artifact found in input_artifacts")

        local_path = image_artifact.get("_local_path") or image_artifact.get("local_path")
        if not local_path or not os.path.isfile(local_path):
            raise FileNotFoundError(f"Input image not found: {local_path}")

        from PIL import Image

        image = Image.open(local_path).convert("RGBA")
        # TripoSR expects RGB; composite onto white background if alpha present.
        if image.mode == "RGBA":
            background = Image.new("RGBA", image.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, image).convert("RGB")

        with _model_lock:
            model = _load_model(model_path)

        device = _get_device()
        logger.info("TripoSR: running inference (resolution=%d)", model_resolution)

        with torch.no_grad():
            scenes = model(
                [image],
                device=device,
                image_size=model_resolution,
            )

        if not scenes or not scenes[0]:
            raise RuntimeError("TripoSR returned no meshes")

        scene = scenes[0]

        output_filename = "triposr_output.glb"
        output_path = os.path.join(output_dir, output_filename)

        # TripoSR scene objects expose an export method.
        # The mesh may be a trimesh.Trimesh or have its own export.
        meshes = scene.meshes if hasattr(scene, "meshes") else [scene]
        vertices_list = []
        faces_list = []
        vertex_offset = 0

        for mesh in meshes:
            verts = mesh.vertices if hasattr(mesh, "vertices") else None
            faces = mesh.faces if hasattr(mesh, "faces") else None
            if verts is None or faces is None:
                continue
            import numpy as np

            vertices_list.append(verts if isinstance(verts, np.ndarray) else np.array(verts))
            f = faces if isinstance(faces, np.ndarray) else np.array(faces)
            faces_list.append(f + vertex_offset)
            vertex_offset += len(vertices_list[-1])

        if not vertices_list:
            raise RuntimeError("TripoSR produced no valid mesh data")

        import numpy as np
        import trimesh

        all_verts = np.concatenate(vertices_list, axis=0)
        all_faces = np.concatenate(faces_list, axis=0)
        combined = trimesh.Trimesh(vertices=all_verts, faces=all_faces, process=True)
        combined.export(output_path, file_type="glb")

        logger.info("TripoSR: saved GLB to %s (%d vertices)", output_path, len(combined.vertices))

        return [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "generator": "triposr",
                "model_path": model_path,
                "model_resolution": model_resolution,
                "vertex_count": len(combined.vertices),
                "face_count": len(combined.faces),
            },
        }]
