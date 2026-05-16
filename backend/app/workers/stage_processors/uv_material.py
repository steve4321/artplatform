from __future__ import annotations

import logging
import os

import numpy as np
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

        texture_paths = _generate_pbr_textures(mesh, texture_resolution, output_dir)
        mesh = _apply_textures_to_mesh(mesh, texture_paths)

        output_filename = "uv_material_output.glb"
        output_path = os.path.join(output_dir, output_filename)
        mesh.export(output_path, file_type="glb")

        logger.info("UV/Material: saved %s", output_path)

        artifacts: list[dict] = [{
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
