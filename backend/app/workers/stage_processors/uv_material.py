from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess

import numpy as np
import trimesh
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

MESH_FORMATS = {"obj", "glb", "gltf", "ply"}

BLENDER_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "blender_scripts", "texture_projection.py"
)


def _find_mesh_artifact(input_artifacts: list[dict]) -> dict | None:
    for artifact in input_artifacts:
        if artifact.get("file_format") in MESH_FORMATS:
            return artifact
    return None


def _find_concept_image(input_artifacts: list[dict]) -> dict | None:
    for artifact in input_artifacts:
        meta = artifact.get("metadata", {})
        if artifact.get("file_format") == "png" and meta.get("source") == "concept_image":
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


def _run_blender_texture_projection(
    blender_bin: str,
    script_path: str,
    mesh_path: str,
    concept_image_path: str,
    output_dir: str,
    timeout: int,
) -> dict:
    cmd = [
        blender_bin,
        "--background",
        "--python", script_path,
        "--",
        mesh_path,
        concept_image_path,
        output_dir,
    ]
    logger.info("Running Blender texture projection: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        stderr_excerpt = result.stderr[-800:] if result.stderr else "(empty)"
        raise RuntimeError(
            f"Blender texture projection failed (exit {result.returncode}): {stderr_excerpt}"
        )

    for line in reversed(result.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in data:
                raise RuntimeError(f"Blender texture projection error: {data['error']}")
            return data

    raise RuntimeError(
        f"Blender texture projection produced no JSON output. stdout:\n{result.stdout[-500:]}"
    )


def _uv_unwrap_xatlas(mesh: trimesh.Trimesh, padding: float = 2.0) -> trimesh.Trimesh:
    import xatlas

    logger.info("xatlas: unwrapping mesh (%d verts, %d faces)", len(mesh.vertices), len(mesh.faces))

    vmapping, indices, uvs = xatlas.parametrize(
        mesh.vertices.copy().astype(np.float32),
        mesh.faces.copy().astype(np.int32),
    )

    atlas = xatlas.Atlas()
    atlas.add_mesh(
        mesh.vertices.copy().astype(np.float32),
        mesh.faces.copy().astype(np.int32),
    )
    atlas.generate(padding=padding)
    vmapping, indices, uvs = atlas[0]

    remeshed = trimesh.Trimesh(
        vertices=mesh.vertices[vmapping],
        faces=indices,
        process=False,
    )
    remeshed.visual = trimesh.visual.TextureVisuals(uv=uvs)

    logger.info("xatlas: produced %d verts, %d faces, UVs shape=%s", len(remeshed.vertices), len(remeshed.faces), uvs.shape)
    return remeshed


def _uv_unwrap_lscm_fallback(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    logger.info("Falling back to basic UV unwrap (trimesh built-in)")

    if not hasattr(mesh, "visual") or not hasattr(mesh.visual, "uv"):
        uv = trimesh.util.unitize(mesh.vertices[:, :2] - mesh.vertices[:, :2].min(axis=0))
        mesh.visual = trimesh.visual.TextureVisuals(uv=uv)

    return mesh


def _generate_pbr_textures(
    mesh: trimesh.Trimesh,
    resolution: int,
    output_dir: str,
    base_color: tuple[int, int, int] | None = None,
) -> dict[str, str]:
    from PIL import Image

    if base_color is None:
        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
            colors = np.array(mesh.visual.vertex_colors)
            mean_color = colors[:, :3].mean(axis=0).astype(int)
            base_color = tuple(mean_color)
        else:
            base_color = (180, 180, 180)

    paths: dict[str, str] = {}

    albedo = Image.new("RGB", (resolution, resolution), base_color)
    albedo_path = os.path.join(output_dir, "albedo.png")
    albedo.save(albedo_path, "PNG")
    paths["albedo"] = albedo_path

    # Neutral blue (128,128,255) = flat normal in OpenGL convention
    normal_data = np.full((resolution, resolution, 3), [128, 128, 255], dtype=np.uint8)
    normal = Image.fromarray(normal_data, "RGB")
    normal_path = os.path.join(output_dir, "normal.png")
    normal.save(normal_path, "PNG")
    paths["normal"] = normal_path

    # Metallic-Roughness (G=roughness=0.5, B=metallic=0.0)
    mr_data = np.full((resolution, resolution, 3), [0, 128, 0], dtype=np.uint8)
    metallic_roughness = Image.fromarray(mr_data, "RGB")
    mr_path = os.path.join(output_dir, "metallic_roughness.png")
    metallic_roughness.save(mr_path, "PNG")
    paths["metallic_roughness"] = mr_path

    logger.info("Generated PBR textures at %dx%d: %s", resolution, resolution, list(paths.keys()))
    return paths


def _apply_textures_to_mesh(
    mesh: trimesh.Trimesh,
    texture_paths: dict[str, str],
) -> trimesh.Trimesh:
    from PIL import Image

    albedo_img = Image.open(texture_paths["albedo"])

    uvs = None
    if hasattr(mesh.visual, "uv") and mesh.visual.uv is not None:
        uvs = mesh.visual.uv

    if uvs is not None:
        material = trimesh.visual.texture.SimpleMaterial(
            image=albedo_img,
        )
        mesh.visual = trimesh.visual.TextureVisuals(
            uv=uvs,
            material=material,
        )

    return mesh


@register
class UVMaterialXatlasBpy(PipelineProcessor):
    stage = "uv_material"
    name = "xatlas_bpy"
    requires_gpu = False
    estimated_duration_s = 45

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return any(
            a.get("file_format") in MESH_FORMATS
            for a in input_artifacts
        )

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        texture_resolution: int = int(config.get("texture_resolution", 1024))
        uv_padding: float = float(config.get("uv_padding", 2.0))

        mesh_artifact = _find_mesh_artifact(input_artifacts)
        if mesh_artifact is None:
            raise ValueError("No mesh artifact found in input_artifacts")

        input_path = _resolve_local_path(mesh_artifact)
        mesh = trimesh.load(input_path, force="mesh")

        logger.info("UV/Material: loaded mesh (%d verts, %d faces)", len(mesh.vertices), len(mesh.faces))

        try:
            mesh = _uv_unwrap_xatlas(mesh, padding=uv_padding)
        except ImportError:
            logger.warning("xatlas not available, using fallback UV unwrap")
            mesh = _uv_unwrap_lscm_fallback(mesh)
        except Exception as exc:
            logger.warning("xatlas failed (%s), using fallback UV unwrap", exc)
            mesh = _uv_unwrap_lscm_fallback(mesh)

        concept_artifact = _find_concept_image(input_artifacts)
        texture_paths: dict[str, str] = {}

        if concept_artifact:
            concept_path = _resolve_local_path(concept_artifact)
            blender_bin = _find_blender_binary(config)
            timeout = int(config.get("texture_projection_timeout", 300))

            if blender_bin and os.path.isfile(os.path.normpath(BLENDER_SCRIPT)):
                uv_mapped_path = os.path.join(output_dir, "uv_mapped_input.glb")
                mesh.export(uv_mapped_path, file_type="glb")

                projection_output_dir = os.path.join(output_dir, "projection_output")
                os.makedirs(projection_output_dir, exist_ok=True)

                try:
                    metadata = _run_blender_texture_projection(
                        blender_bin,
                        os.path.normpath(BLENDER_SCRIPT),
                        uv_mapped_path,
                        concept_path,
                        projection_output_dir,
                        timeout,
                    )

                    baked_albedo = metadata.get("albedo_path", "")
                    projected_glb = metadata.get("output_path", "")

                    if baked_albedo and os.path.isfile(baked_albedo):
                        texture_paths["albedo"] = baked_albedo
                        logger.info("Using baked albedo from texture projection: %s", baked_albedo)

                    if projected_glb and os.path.isfile(projected_glb):
                        normal_path = os.path.join(output_dir, "normal.png")
                        mr_path = os.path.join(output_dir, "metallic_roughness.png")
                        from PIL import Image

                        normal_data = np.full((texture_resolution, texture_resolution, 3), [128, 128, 255], dtype=np.uint8)
                        Image.fromarray(normal_data, "RGB").save(normal_path, "PNG")
                        texture_paths["normal"] = normal_path

                        mr_data = np.full((texture_resolution, texture_resolution, 3), [0, 128, 0], dtype=np.uint8)
                        Image.fromarray(mr_data, "RGB").save(mr_path, "PNG")
                        texture_paths["metallic_roughness"] = mr_path

                        output_path = os.path.join(output_dir, "uv_material_output.glb")
                        shutil.copy2(projected_glb, output_path)

                        artifacts: list[dict] = [{
                            "local_path": output_path,
                            "file_format": "glb",
                            "content_type": "model/gltf-binary",
                            "metadata": {
                                "generator": "xatlas_bpy",
                                "texture_projection": True,
                                "texture_resolution": texture_resolution,
                                "uv_padding": uv_padding,
                                "vertex_count": len(mesh.vertices),
                                "face_count": len(mesh.faces),
                            },
                        }]

                        for tex_name, tex_path in texture_paths.items():
                            artifacts.append({
                                "local_path": tex_path,
                                "file_format": "png",
                                "content_type": "image/png",
                                "metadata": {
                                    "texture_type": tex_name,
                                    "resolution": texture_resolution,
                                },
                            })

                        logger.info("UV/Material: texture projection complete, output %s", output_path)
                        return artifacts

                except Exception as exc:
                    logger.warning("Texture projection failed (%s), falling back to flat color", exc)
            else:
                logger.info("Blender not available, skipping texture projection")

        texture_paths = _generate_pbr_textures(mesh, texture_resolution, output_dir)
        mesh = _apply_textures_to_mesh(mesh, texture_paths)

        output_filename = "uv_material_output.glb"
        output_path = os.path.join(output_dir, output_filename)
        mesh.export(output_path, file_type="glb")

        logger.info("UV/Material: saved %s", output_path)

        artifacts = [{
            "local_path": output_path,
            "file_format": "glb",
            "content_type": "model/gltf-binary",
            "metadata": {
                "generator": "xatlas_bpy",
                "texture_resolution": texture_resolution,
                "uv_padding": uv_padding,
                "vertex_count": len(mesh.vertices),
                "face_count": len(mesh.faces),
            },
        }]

        for tex_name, tex_path in texture_paths.items():
            artifacts.append({
                "local_path": tex_path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "texture_type": tex_name,
                    "resolution": texture_resolution,
                },
            })

        return artifacts
