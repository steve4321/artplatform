"""2D format output stage: PNG, Sprite Sheet, or Android 9-Patch."""

from __future__ import annotations

import json
import logging
import os

from PIL import Image
from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}


def _find_image_artifacts(input_artifacts: list[dict]) -> list[dict]:
    return [a for a in input_artifacts if a.get("file_format") in IMAGE_FORMATS]


def _resolve_local_path(artifact: dict) -> str:
    path = artifact.get("_local_path") or artifact.get("local_path")
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"Input image not found: {path}")
    return path


def _output_png(images: list[Image.Image], output_dir: str, padding: int) -> list[dict]:
    results: list[dict] = []
    for idx, img in enumerate(images):
        if padding > 0:
            new_w = img.width + padding * 2
            new_h = img.height + padding * 2
            padded = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
            padded.paste(img, (padding, padding), img if img.mode == "RGBA" else None)
            img = padded

        out_path = os.path.join(output_dir, f"output_{idx}.png")
        img.save(out_path, "PNG")
        results.append({
            "local_path": out_path,
            "file_format": "png",
            "content_type": "image/png",
            "metadata": {
                "generator": "png_sprite_9patch",
                "output_type": "png",
                "width": img.width,
                "height": img.height,
                "index": idx,
            },
        })
    return results


def _output_sprite_sheet(images: list[Image.Image], output_dir: str, padding: int) -> list[dict]:
    if not images:
        raise ValueError("No images to arrange into sprite sheet")

    frame_w = images[0].width + padding * 2
    frame_h = images[0].height + padding * 2
    total_w = frame_w * len(images)
    total_h = frame_h

    sheet = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    frames_meta: list[dict] = []

    for idx, img in enumerate(images):
        x = idx * frame_w + padding
        y = padding
        sheet.paste(img, (x, y), img if img.mode == "RGBA" else None)
        frames_meta.append({
            "filename": f"frame_{idx}",
            "frame": {"x": x, "y": y, "w": images[0].width, "h": images[0].height},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": images[0].width, "h": images[0].height},
            "sourceSize": {"w": images[0].width, "h": images[0].height},
        })

    sheet_path = os.path.join(output_dir, "sprite_sheet.png")
    sheet.save(sheet_path, "PNG")

    atlas = {
        "frames": frames_meta,
        "meta": {
            "image": "sprite_sheet.png",
            "size": {"w": total_w, "h": total_h},
            "scale": 1,
            "frame_count": len(images),
        },
    }
    atlas_path = os.path.join(output_dir, "sprite_atlas.json")
    with open(atlas_path, "w", encoding="utf-8") as f:
        json.dump(atlas, f, indent=2)

    return [
        {
            "local_path": sheet_path,
            "file_format": "png",
            "content_type": "image/png",
            "metadata": {
                "generator": "png_sprite_9patch",
                "output_type": "sprite_sheet",
                "width": total_w,
                "height": total_h,
                "frame_count": len(images),
            },
        },
        {
            "local_path": atlas_path,
            "file_format": "json",
            "content_type": "application/json",
            "metadata": {
                "generator": "png_sprite_9patch",
                "output_type": "sprite_atlas",
                "frame_count": len(images),
            },
        },
    ]


def _output_9patch(images: list[Image.Image], output_dir: str, padding: int) -> list[dict]:
    if len(images) != 1:
        logger.warning("9-patch expects exactly 1 image, got %d — using first image only", len(images))

    img = images[0].convert("RGBA")
    new_w = img.width + 2
    new_h = img.height + 2
    nine = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))

    nine.paste(img, (1, 1))

    black = (0, 0, 0, 255)
    mid_x = new_w // 2
    mid_y = new_h // 2
    for x in range(1, new_w - 1):
        nine.putpixel((x, 0), black)
        nine.putpixel((x, new_h - 1), black)
    for y in range(1, new_h - 1):
        nine.putpixel((0, y), black)
        nine.putpixel((new_w - 1, y), black)

    out_path = os.path.join(output_dir, "output.9.png")
    nine.save(out_path, "PNG")

    return [{
        "local_path": out_path,
        "file_format": "png",
        "content_type": "image/png",
        "metadata": {
            "generator": "png_sprite_9patch",
            "output_type": "9patch",
            "width": new_w,
            "height": new_h,
            "content_width": img.width,
            "content_height": img.height,
        },
    }]


@register
class FormatOutput2D(PipelineProcessor):
    stage = "format_output"
    name = "png_sprite_9patch"
    requires_gpu = False
    estimated_duration_s = 3

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        return bool(_find_image_artifacts(input_artifacts))

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        output_type: str = config.get("output_type", "png")
        padding: int = int(config.get("padding", 0))

        image_artifacts = _find_image_artifacts(input_artifacts)
        if not image_artifacts:
            raise ValueError("No image artifacts found in input_artifacts")

        os.makedirs(output_dir, exist_ok=True)

        images: list[Image.Image] = []
        for artifact in image_artifacts:
            input_path = _resolve_local_path(artifact)
            images.append(Image.open(input_path).convert("RGBA"))

        logger.info("FormatOutput2D: processing %d images as '%s'", len(images), output_type)

        if output_type == "sprite_sheet":
            results = _output_sprite_sheet(images, output_dir, padding)
        elif output_type == "9patch":
            results = _output_9patch(images, output_dir, padding)
        else:
            results = _output_png(images, output_dir, padding)

        logger.info("FormatOutput2D: produced %d artifacts", len(results))
        return results
