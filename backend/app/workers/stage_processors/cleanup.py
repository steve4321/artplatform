from __future__ import annotations

import logging
import os
import shutil
import subprocess

import trimesh
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

MESH_FORMATS = {"obj", "glb", "gltf", "ply"}


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


def _find_instant_meshes_binary(config: dict) -> str | None:
    config_path = config.get("instant_meshes_binary")
    if config_path and os.path.isfile(config_path):
        return config_path
    found = shutil.which("instant_meshes")
    return found


def _run_instant_meshes(
    input_path: str, output_path: str, target_faces: int, binary: str
) -> None:
    cmd = [
        binary,
        input_path,
        "-o", output_path,
        "-f", str(target_faces),
        "--smooth",
    ]
    logger.info("Running Instant Meshes: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(
            f"Instant Meshes failed (exit {result.returncode}): {result.stderr[:500]}"
        )


def _run_pymeshlab_cleanup(
    input_path: str, output_path: str, target_faces: int, smooth_iterations: int
) -> None:
    import pymeshlab

    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(input_path)
    mesh = ms.current_mesh()

    logger.info(
        "pymeshlab: loaded %d faces, target=%d, smooth=%d",
        mesh.face_number(), target_faces, smooth_iterations,
    )

    ms.apply_filter("meshing_remove_duplicate_vertices")
    ms.apply_filter("meshing_remove_duplicate_faces")
    ms.apply_filter("meshing_remove_null_faces")

    current_faces = ms.current_mesh().face_number()
    if current_faces > target_faces:
        ratio = target_faces / current_faces
        decimation_filter = (
            "meshing_decimation_quadric_edge_collapse_with_texture"
            if ms.current_mesh().has_wedge_tex_coord()
            else "meshing_decimation_quadric_edge_collapse"
        )
        ms.apply_filter(
            decimation_filter,
            targetfacenum=int(current_faces * ratio),
        )

    if smooth_iterations > 0:
        ms.apply_filter("apply_coord_laplacian_smoothing", stepsmoothnum=smooth_iterations)

    output_ext = os.path.splitext(output_path)[1].lower()
    if output_ext in (".glb", ".gltf"):
        ply_tmp = output_path.rsplit(".", 1)[0] + "_tmp.ply"
        ms.save_current_mesh(ply_tmp)
        cleaned = trimesh.load(ply_tmp, force="mesh")
        cleaned.export(output_path, file_type="glb")
        os.remove(ply_tmp)
    else:
        ms.save_current_mesh(output_path)

    logger.info("pymeshlab: saved to %s", output_path)


@register
class CleanupInstantMeshes(PipelineProcessor):
    stage = "mesh_cleanup"
    name = "instant_meshes"
    requires_gpu = False
    estimated_duration_s = 20

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in MESH_FORMATS
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        target_face_count: int = int(config.get("target_face_count", 10000))
        smooth_iterations: int = int(config.get("smooth_iterations", 3))

        mesh_artifact = _find_mesh_artifact(input_artifacts)
        if mesh_artifact is None:
            raise ValueError("No mesh artifact found in input_artifacts")

        input_path = _resolve_local_path(mesh_artifact)
        input_ext = os.path.splitext(input_path)[1].lower()

        # Instant Meshes prefers OBJ input; convert if necessary.
        instant_meshes_input = input_path
        if input_ext not in (".obj",):
            obj_path = os.path.join(output_dir, "_im_input.obj")
            scene = trimesh.load(input_path, force="mesh")
            scene.export(obj_path, file_type="obj")
            instant_meshes_input = obj_path

        output_filename = "cleanup_output.glb"
        output_path = os.path.join(output_dir, output_filename)

        binary = _find_instant_meshes_binary(config)

        if binary:
            im_output = os.path.join(output_dir, "_im_output.obj")
            _run_instant_meshes(instant_meshes_input, im_output, target_face_count, binary)

            scene = trimesh.load(im_output, force="mesh")
            scene.export(output_path, file_type="glb")
        else:
            logger.info("Instant Meshes binary not found, falling back to pymeshlab")
            _run_pymeshlab_cleanup(input_path, output_path, target_face_count, smooth_iterations)

        final_scene = trimesh.load(output_path, force="mesh")
        vertex_count = len(final_scene.vertices) if hasattr(final_scene, "vertices") else 0
        face_count = len(final_scene.faces) if hasattr(final_scene, "faces") else 0

        logger.info("Cleanup: saved %s (%d verts, %d faces)", output_path, vertex_count, face_count)

        return [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "generator": "instant_meshes" if binary else "pymeshlab",
                "target_face_count": target_face_count,
                "smooth_iterations": smooth_iterations,
                "vertex_count": vertex_count,
                "face_count": face_count,
            },
        }]
