"""2D post-processing stage: remove background, resize, optional Real-ESRGAN upscale."""

from __future__ import annotations

import io
import logging
import os

from PIL import Image
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}

_REALESRGAN_AVAILABLE = False
try:
    from realesrgan import RealESRGANer
    from basicsr.archs.rrdbnet_arch import RRDBNet
    _REALESRGAN_AVAILABLE = True
except ImportError:
    logger.info("Real-ESRGAN not available — upscale will be skipped")


def _find_image_artifacts(input_artifacts: list[dict]) -> list[dict]:
    return [a for a in input_artifacts if a.get("file_format") in IMAGE_FORMATS]


def _resolve_local_path(artifact: dict) -> str:
    path = artifact.get("_local_path") or artifact.get("local_path")
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Input image not found: {path}")
    return path


def _parse_target_size(size_str: str) -> tuple[int, int]:
    """Parse a target size string like '512x512' into (width, height)."""
    parts = size_str.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid target_size format: {size_str!r}. Expected 'WxH' (e.g. '512x512')")
    return int(parts[0]), int(parts[1])


def _remove_background(image: Image.Image) -> Image.Image:
    """Remove image background using rembg."""
    from rembg import remove

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    input_bytes = buf.getvalue()

    output_bytes = remove(input_bytes)
    return Image.open(io.BytesIO(output_bytes)).convert("RGBA")


def _upscale_image(image: Image.Image, scale: int) -> Image.Image:
    """Upscale image using Real-ESRGAN. Returns original if unavailable."""
    if not _REALESRGAN_AVAILABLE:
        logger.warning("Real-ESRGAN not available, skipping upscale")
        return image

    import numpy as np

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=scale)
    upsampler = RealESRGANer(
        scale=scale,
        model_path=None,
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=False,
    )

    img_array = np.array(image.convert("RGB"))
    output, _ = upsampler.enhance(img_array, outscale=scale)
    return Image.fromarray(output).convert("RGBA")


@register
class Postprocess2D(PipelineProcessor):
    stage = "postprocess_2d"
    name = "rembg_esrgan"
    requires_gpu = False
    estimated_duration_s = 10

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(_find_image_artifacts(input_artifacts))

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        target_size_str: str = config.get("target_size", "512x512")
        remove_background: bool = config.get("remove_background", True)
        upscale_factor: int = int(config.get("upscale_factor", 1))

        target_w, target_h = _parse_target_size(target_size_str)
        image_artifacts = _find_image_artifacts(input_artifacts)

        if not image_artifacts:
            raise ValueError("No image artifacts found in input_artifacts")

        results: list[dict] = []
        os.makedirs(output_dir, exist_ok=True)
        for idx, artifact in enumerate(image_artifacts):
            input_path = _resolve_local_path(artifact)
            image = Image.open(input_path).convert("RGBA")
            logger.info("Postprocess2D: loaded %s (mode=%s, size=%s)", input_path, image.mode, image.size)

            if remove_background:
                try:
                    image = _remove_background(image)
                    logger.info("Postprocess2D: background removed for image %d", idx)
                except Exception as exc:
                    logger.warning("rembg failed for image %d (%s), keeping original", idx, exc)

            image = image.resize((target_w, target_h), Image.LANCZOS)
            logger.info("Postprocess2D: resized to %dx%d", target_w, target_h)

            if upscale_factor > 1:
                try:
                    image = _upscale_image(image, upscale_factor)
                    logger.info("Postprocess2D: upscaled %dx for image %d", upscale_factor, idx)
                except Exception as exc:
                    logger.warning("Real-ESRGAN upscale failed for image %d (%s), skipping", idx, exc)

            out_filename = f"postprocessed_{idx}.png"
            out_path = os.path.join(output_dir, out_filename)
            image.save(out_path, "PNG")

            results.append({
                "local_path": out_path,
                "file_format": "png",
                "content_type": "image/png",
                "metadata": {
                    "generator": "rembg_esrgan",
                    "target_size": target_size_str,
                    "remove_background": remove_background,
                    "upscale_factor": upscale_factor,
                    "actual_size": f"{image.width}x{image.height}",
                    "source_index": idx,
                },
            })

        logger.info("Postprocess2D: produced %d processed images", len(results))
        return results
