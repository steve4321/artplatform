"""Animation processors — Mixamo BVH presets + HY-Motion self-hosted."""

from __future__ import annotations

import logging
import os

import bpy

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)


@register
class MixamoPresetProcessor(PipelineProcessor):
    """Apply pre-downloaded Mixamo BVH animation presets to rigged characters.

    Env vars:
        MIXAMO_PRESETS_DIR — directory containing .bvh preset files
            (e.g. /data/resources/presets/idle.bvh, walk.bvh, run.bvh, ...)
    """

    stage = "animate"
    name = "mixamo_preset"
    requires_gpu = False
    estimated_duration_s = 5

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        has_mesh = any(a.get("file_format") in ("glb", "fbx") for a in input_artifacts)
        has_preset = bool(config.get("animation_preset", "idle"))
        return has_mesh and has_preset

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        preset = config.get("animation_preset", "idle")
        presets_dir = config.get("presets_dir", os.environ.get("MIXAMO_PRESETS_DIR", "/data/resources/presets"))
        bvh_path = os.path.join(presets_dir, f"{preset}.bvh")

        if not os.path.exists(bvh_path):
            raise FileNotFoundError(
                f"Mixamo BVH preset not found: {bvh_path}. "
                "Download presets to MIXAMO_PRESETS_DIR/"
            )

        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "fbx")),
            None,
        )
        if not mesh_artifact:
            raise ValueError("No rigged mesh found for animation")

        input_path = mesh_artifact.get("_local_path") or mesh_artifact.get("local_path")

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".glb":
            bpy.ops.import_scene.gltf(filepath=input_path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=input_path)
        else:
            raise ValueError(f"Unsupported mesh format: {ext}")

        obj = bpy.context.selected_objects[0]
        bpy.context.view_layer.objects.active = obj

        try:
            bpy.ops.import_anim.bvh(filepath=bvh_path, target="ARMATURE", scale_duration=1.0)
        except Exception as exc:
            raise RuntimeError(f"Failed to import BVH '{preset}': {exc}") from exc

        if obj.animation_data is None:
            obj.animation_data_create()
        src = bpy.context.selected_objects[0]
        if src.animation_data and src.animation_data.action:
            obj.animation_data.action = src.animation_data.action

        output_glb = os.path.join(output_dir, f"animated_{preset}.glb")
        bpy.ops.export_scene.gltf(
            filepath=output_glb,
            export_format="GLB",
            export_animations=True,
            export_skins=True,
            export_bones=True,
        )

        output_fbx = os.path.join(output_dir, f"animated_{preset}.fbx")
        bpy.ops.export_scene.fbx(
            filepath=output_fbx,
            use_selection=False,
            bake_anim=True,
            armature_type="EXPORT",
        )

        logger.info("Mixamo preset '%s' applied", preset)

        artifacts = [
            {
                "local_path": output_glb,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {"animation_preset": preset, "animation_clips": 1, "generator": "mixamo_preset"},
            }
        ]
        if os.path.exists(output_fbx):
            artifacts.append({
                "local_path": output_fbx,
                "file_format": "fbx",
                "content_type": "application/octet-stream",
                "metadata": {"format": "unity_fbx_with_animation"},
            })

        return artifacts


@register
class HYMotionSelfHostedProcessor(PipelineProcessor):
    """HY-Motion 1.0 Lite self-hosted inference via HTTP server.

    Calls an external HY-Motion HTTP server (recommended) or loads model inline.

    Env vars:
        HYMOTION_SERVER_URL — HTTP server URL (e.g. http://localhost:8003)
        HYMOTION_MODEL_PATH — local model path (inline mode)
    """

    stage = "animate"
    name = "hy_motion_self_hosted"
    requires_gpu = True
    estimated_duration_s = 25

    def __init__(self):
        self.server_url = os.environ.get("HYMOTION_SERVER_URL", "http://localhost:8003")
        self.use_http = bool(self.server_url)
        self._model = None

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        has_mesh = any(a.get("file_format") in ("glb", "fbx") for a in input_artifacts)
        has_prompt = bool(config.get("animation_prompt") or config.get("prompt"))
        return has_mesh and has_prompt

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        import uuid

        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "fbx")),
            None,
        )
        if not mesh_artifact:
            raise ValueError("No rigged mesh for animation")

        input_path = mesh_artifact.get("_local_path") or mesh_artifact.get("local_path")
        prompt = config.get("animation_prompt", config.get("prompt", "idle"))
        num_frames = int(config.get("num_frames", 60))
        fps = int(config.get("fps", 30))

        bvh_path = os.path.join(output_dir, f"motion_{uuid.uuid4().hex}.bvh")

        if self.use_http:
            import httpx
            resp = httpx.post(
                f"{self.server_url}/generate",
                json={"prompt": prompt, "num_frames": num_frames, "fps": fps},
                timeout=120,
            )
            resp.raise_for_status()
            with open(bvh_path, "wb") as f:
                f.write(resp.content)
        else:
            bvh_path = self._generate_inline(prompt, num_frames, fps, output_dir)

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".glb":
            bpy.ops.import_scene.gltf(filepath=input_path)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=input_path)

        obj = bpy.context.selected_objects[0]
        bpy.context.view_layer.objects.active = obj

        try:
            bpy.ops.import_anim.bvh(filepath=bvh_path, target="ARMATURE")
        except Exception as exc:
            logger.warning("BVH import warning: %s", exc)

        output_glb = os.path.join(output_dir, "animated_output.glb")
        bpy.ops.export_scene.gltf(
            filepath=output_glb,
            export_format="GLB",
            export_animations=True,
            export_skins=True,
        )

        output_fbx = os.path.join(output_dir, "animated_output.fbx")
        bpy.ops.export_scene.fbx(
            filepath=output_fbx,
            use_selection=False,
            bake_anim=True,
            armature_type="EXPORT",
        )

        logger.info("HY-Motion generated animation for '%s…'", prompt[:50])

        artifacts = [
            {
                "local_path": output_glb,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {
                    "animation_prompt": prompt,
                    "num_frames": num_frames,
                    "fps": fps,
                    "generator": "hy_motion_self_hosted",
                },
            },
            {
                "local_path": output_fbx,
                "file_format": "fbx",
                "content_type": "application/octet-stream",
                "metadata": {"format": "unity_fbx_with_animation"},
            },
        ]

        return artifacts

    def _generate_inline(self, prompt: str, num_frames: int, fps: int, output_dir: str) -> str:
        import uuid
        import torch

        if self._model is None:
            from hymotion.models import HYMotionPipeline

            model_path = os.environ.get("HYMOTION_MODEL_PATH", "hymotion/HY-Motion-1.0-Lite")
            self._model = HYMotionPipeline.from_pretrained(model_path, torch_dtype=torch.float16)
            self._model = self._model.to("cuda")

        with torch.no_grad():
            motion = self._model(prompt=prompt, num_frames=num_frames, fps=fps)

        bvh_path = os.path.join(output_dir, f"motion_{uuid.uuid4().hex}.bvh")
        motion.save_bvh(bvh_path)

        if os.environ.get("UNLOAD_MODEL_AFTER_STAGE", "true").lower() == "true":
            del self._model
            self._model = None
            torch.cuda.empty_cache()

        return bvh_path
