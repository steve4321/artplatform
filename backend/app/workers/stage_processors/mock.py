from __future__ import annotations

import json
import logging
import os
import struct
import time
import uuid
import zlib

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)


def _write_fake_image(path: str, width: int = 256, height: int = 256) -> None:
    """Write a minimal valid PNG file (white pixels)."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    ihdr = _chunk(b"IHDR", ihdr_data)

    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"  # filter byte
        raw_data += b"\xff\xff\xff" * width  # white pixels

    compressed = zlib.compress(raw_data)
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(signature + ihdr + idat + iend)


def _write_fake_glb(path: str) -> None:
    """Write a minimal valid GLB file with a tiny triangle mesh."""

    gltf_json = {
        "asset": {"version": "2.0", "generator": "ArtPlatform Mock"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "max": [[1, 1, 0]],
                "min": [[-1, -1, 0]],
            },
            {"bufferView": 1, "componentType": 5125, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 12},
        ],
        "buffers": [{"byteLength": 48}],
    }

    json_str = json.dumps(gltf_json, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    # Pad to 4-byte boundary
    json_bytes += b" " * (4 - len(json_bytes) % 4) if len(json_bytes) % 4 else b""

    # Binary: 3 vertices (9 floats) + 3 indices (3 uint32s)
    verts = struct.pack("9f", -1, -1, 0, 1, -1, 0, 0, 1, 0)
    indices = struct.pack("3I", 0, 1, 2)
    bin_data = verts + indices

    json_chunk = struct.pack(">I", len(json_bytes)) + b"JSON" + json_bytes
    bin_chunk = struct.pack(">I", len(bin_data)) + b"BIN\0" + bin_data

    total = 12 + len(json_chunk) + len(bin_chunk)
    header = struct.pack(">I", total) + struct.pack("<I", 2) + b"glTF"

    with open(path, "wb") as f:
        f.write(header + json_chunk + bin_chunk)


def _copy_or_fake_glb(mesh_artifact: dict | None, output_dir: str, filename: str) -> str:
    """Copy a GLB from a previous artifact, or write a fake one."""
    import shutil

    path = os.path.join(output_dir, filename)
    if mesh_artifact:
        src = mesh_artifact.get("_local_path") or mesh_artifact.get("local_path")
        if src and os.path.isfile(src):
            shutil.copy2(src, path)
            return path
    _write_fake_glb(path)
    return path


class MockPipelineProcessor(PipelineProcessor):
    """Base class for mock processors that simulate pipeline stages with delays."""

    requires_gpu = False
    estimated_duration_s = 1

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return True

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        delay = config.get("mock_delay", 0.2)
        time.sleep(delay)
        return self._produce_output(input_artifacts, config, output_dir)

    def _produce_output(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        raise NotImplementedError


@register
class MockTextToImage(MockPipelineProcessor):
    stage = "text_to_image"
    name = "sdxl_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        prompt = config.get("prompt", "mock")
        images = []
        num = config.get("num_images", 2)
        for i in range(num):
            path = os.path.join(output_dir, f"mock_image_{i}.png")
            _write_fake_image(path, 256, 256)
            images.append(
                {
                    "local_path": path,
                    "file_format": "png",
                    "content_type": "image/png",
                    "metadata": {"prompt": prompt, "index": i, "generator": "mock"},
                }
            )
        logger.info("MockTextToImage: generated %d images", len(images))
        return images


@register
class MockImageTo3D(MockPipelineProcessor):
    stage = "image_to_3d"
    name = "triposr_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        path = os.path.join(output_dir, "mock_model.glb")
        _write_fake_glb(path)
        logger.info("MockImageTo3D: generated GLB")
        return [
            {
                "local_path": path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {"vertex_count": 3, "face_count": 1, "generator": "mock"},
            }
        ]


@register
class MockCleanup(MockPipelineProcessor):
    stage = "cleanup"
    name = "instant_meshes_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf")),
            input_artifacts[0] if input_artifacts else None,
        )
        path = _copy_or_fake_glb(mesh_artifact, output_dir, "cleanup_output.glb")
        logger.info("MockCleanup: produced cleaned mesh")
        return [
            {
                "local_path": path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {"vertex_count": 3, "face_count": 1, "generator": "mock"},
            }
        ]


@register
class MockUVMaterial(MockPipelineProcessor):
    stage = "uv_material"
    name = "xatlas_bpy_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf")),
            input_artifacts[0] if input_artifacts else None,
        )
        glb_path = _copy_or_fake_glb(mesh_artifact, output_dir, "uv_output.glb")

        _write_fake_image(os.path.join(output_dir, "albedo.png"), 64, 64)
        _write_fake_image(os.path.join(output_dir, "normal.png"), 64, 64)
        _write_fake_image(os.path.join(output_dir, "metallic_roughness.png"), 64, 64)

        logger.info("MockUVMaterial: produced mesh + textures")
        return [
            {
                "local_path": glb_path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {"generator": "mock", "texture_resolution": 64},
            },
            {
                "local_path": os.path.join(output_dir, "albedo.png"),
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {"texture_type": "albedo"},
            },
            {
                "local_path": os.path.join(output_dir, "normal.png"),
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {"texture_type": "normal"},
            },
            {
                "local_path": os.path.join(output_dir, "metallic_roughness.png"),
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {"texture_type": "metallic_roughness"},
            },
        ]


@register
class MockRig(MockPipelineProcessor):
    stage = "rig"
    name = "rigify_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf")),
            input_artifacts[0] if input_artifacts else None,
        )
        path = _copy_or_fake_glb(mesh_artifact, output_dir, "rigged_output.glb")
        logger.info("MockRig: produced rigged mesh")
        return [
            {
                "local_path": path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {"bone_count": 22, "generator": "mock"},
            }
        ]


@register
class MockAnimate(MockPipelineProcessor):
    stage = "animate"
    name = "hy_motion_mock"
    estimated_duration_s = 2

    def _produce_output(self, input_artifacts, config, output_dir):
        mesh_artifact = next(
            (a for a in input_artifacts if a.get("file_format") in ("glb", "obj", "gltf", "fbx")),
            input_artifacts[0] if input_artifacts else None,
        )
        path = _copy_or_fake_glb(mesh_artifact, output_dir, "animated_output.glb")
        logger.info("MockAnimate: produced animated mesh")
        return [
            {
                "local_path": path,
                "file_format": "glb",
                "content_type": "model/gltf-binary",
                "metadata": {"animation_clips": 1, "generator": "mock"},
            }
        ]


@register
class MockPostprocess2D(MockPipelineProcessor):
    stage = "postprocess_2d"
    name = "rembg_esrgan_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        target_size = config.get("target_size", "512x512")
        remove_bg = config.get("remove_background", True)
        upscale = config.get("upscale_factor", 1)

        image_artifacts = [
            a for a in input_artifacts if a.get("file_format") in ("png", "jpg", "jpeg", "webp")
        ]
        if not image_artifacts:
            image_artifacts = [{"file_format": "png"}] if not input_artifacts else input_artifacts

        results = []
        for idx in range(max(len(image_artifacts), 1)):
            path = os.path.join(output_dir, f"postprocessed_{idx}.png")
            _write_fake_image(path, 512, 512)
            results.append({
                "local_path": path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "generator": "mock",
                    "target_size": target_size,
                    "remove_background": remove_bg,
                    "upscale_factor": upscale,
                    "source_index": idx,
                },
            })
        logger.info("MockPostprocess2D: produced %d images", len(results))
        return results


@register
class MockFormatOutput2D(MockPipelineProcessor):
    stage = "format_output_2d"
    name = "png_sprite_9patch_mock"

    def _produce_output(self, input_artifacts, config, output_dir):
        output_type = config.get("output_type", "png")
        padding = config.get("padding", 0)

        image_artifacts = [
            a for a in input_artifacts if a.get("file_format") in ("png", "jpg", "jpeg", "webp")
        ]
        if not image_artifacts:
            image_artifacts = [{"file_format": "png"}] if not input_artifacts else input_artifacts

        results = []
        if output_type == "sprite_sheet":
            sheet_path = os.path.join(output_dir, "sprite_sheet.png")
            _write_fake_image(sheet_path, 512, 256)
            results.append({
                "local_path": sheet_path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "generator": "mock",
                    "output_type": "sprite_sheet",
                    "frame_count": len(image_artifacts) or 1,
                },
            })
            import json as _json
            atlas_path = os.path.join(output_dir, "sprite_atlas.json")
            with open(atlas_path, "w") as f:
                _json.dump({"frames": [], "meta": {"image": "sprite_sheet.png"}}, f)
            results.append({
                "local_path": atlas_path,
                "file_format": "json",
                "content_type": "application/json",
                "metadata": {"generator": "mock", "output_type": "sprite_atlas"},
            })
        elif output_type == "9patch":
            path = os.path.join(output_dir, "output.9.png")
            _write_fake_image(path, 514, 514)
            results.append({
                "local_path": path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {"generator": "mock", "output_type": "9patch"},
            })
        else:
            for idx in range(max(len(image_artifacts), 1)):
                path = os.path.join(output_dir, f"output_{idx}.png")
                _write_fake_image(path, 512, 512)
                results.append({
                    "local_path": path,
                    "file_format": "png",
                    "content_type": "image/png",
                    "metadata": {
                        "generator": "mock",
                        "output_type": "png",
                        "index": idx,
                    },
                })

        logger.info("MockFormatOutput2D: produced %d artifacts as '%s'", len(results), output_type)
        return results
