from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

MESH_FORMATS = {"obj", "glb", "gltf", "fbx"}

BLENDER_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "blender_scripts", "rigify_auto.py"
)


def _find_mesh_artifact(input_artifacts: list[dict]) -> dict | None:
    for artifact in input_artifacts:
        if artifact.get("file_format") in MESH_FORMATS:
            return artifact
    return None


def _resolve_local_path(artifact: dict) -> str:
    path = artifact.get("_local_path") or artifact.get("local_path")
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Input mesh not found: {path}")
    return path


def _find_blender_binary(config: dict) -> str | None:
    config_path = config.get("blender_binary")
    if config_path and os.path.isfile(config_path):
        return config_path
    return shutil.which("blender")


def _run_blender_rig(
    blender_bin: str,
    script_path: str,
    input_path: str,
    output_path: str,
    timeout: int,
) -> dict:
    cmd = [
        blender_bin,
        "--background",
        "--python", script_path,
        "--",
        input_path,
        output_path,
    ]
    logger.info("Running Blender rig: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        stderr_excerpt = result.stderr[-800:] if result.stderr else "(empty)"
        raise RuntimeError(
            f"Blender rig script failed (exit {result.returncode}): {stderr_excerpt}"
        )

    for line in reversed(result.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in data:
                raise RuntimeError(f"Blender rig error: {data['error']}")
            return data

    raise RuntimeError(
        f"Blender rig script produced no JSON output. stdout:\n{result.stdout[-500:]}"
    )


@register
class RigRigify(PipelineProcessor):
    stage = "rig"
    name = "rigify"
    requires_gpu = False
    estimated_duration_s = 60

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        if not _find_blender_binary(config):
            return False
        return any(
            a.get("file_format") in MESH_FORMATS
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        timeout = int(config.get("rig_timeout", 300))

        mesh_artifact = _find_mesh_artifact(input_artifacts)
        if mesh_artifact is None:
            raise ValueError("No mesh artifact found in input_artifacts")

        input_path = _resolve_local_path(mesh_artifact)

        blender_bin = _find_blender_binary(config)
        if blender_bin is None:
            raise RuntimeError("Blender binary not found (checked config and PATH)")

        script_path = os.path.normpath(BLENDER_SCRIPT)
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"Blender rig script not found: {script_path}")

        output_filename = "rigged_output.glb"
        output_path = os.path.join(output_dir, output_filename)

        os.makedirs(output_dir, exist_ok=True)

        metadata = _run_blender_rig(blender_bin, script_path, input_path, output_path, timeout)

        if not os.path.isfile(output_path):
            raise RuntimeError(f"Blender rig script completed but output file missing: {output_path}")

        logger.info(
            "Rig complete: %s (bones=%s, vertex_groups=%s, rig_type=%s)",
            output_path,
            metadata.get("bone_count"),
            metadata.get("vertex_groups"),
            metadata.get("rig_type"),
        )

        return [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "generator": metadata.get("rig_type", "unknown"),
                "bone_count": metadata.get("bone_count", 0),
                "vertex_groups": metadata.get("vertex_groups", 0),
                "mesh_height": metadata.get("mesh_height", 0),
            },
        }]
