"""Image captioning processor — generates prompt suggestions from a reference image."""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

import torch
from PIL import Image

from app.pipeline.processor import PipelineProcessor
from app.pipeline.registry import register

logger = logging.getLogger(__name__)

# Module-level model cache – loaded once, reused across calls.
_pipeline = None
_pipeline_lock = threading.Lock()
_device: str | None = None


def _get_device() -> str:
    global _device
    if _device is None:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("BLIP-2 device: %s", _device)
    return _device


def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    from transformers import Blip2ForConditionalGeneration, BlipProcessor

    device = _get_device()
    logger.info("Loading BLIP-2 model on %s …", device)

    processor = BlipProcessor.from_pretrained("Salesforce/blip2-opt-2.7b")
    model = Blip2ForConditionalGeneration.from_pretrained(
        "Salesforce/blip2-opt-2.7b",
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    )
    model = model.to(device)
    model.eval()

    _pipeline = {"processor": processor, "model": model}
    return _pipeline


@register
class ImageCaptioningBLIP2(PipelineProcessor):
    stage = "image_captioning"
    name = "blip2"
    requires_gpu = False
    estimated_duration_s = 20

    def can_run(self, input_artifacts: list[dict], config: dict) -> bool:
        if not input_artifacts:
            return False
        fmt = input_artifacts[0].get("file_format", "").lower()
        return fmt in ("png", "jpg", "jpeg", "webp")

    def run(self, input_artifacts: list[dict], config: dict, output_dir: str) -> list[dict]:
        image_path = input_artifacts[0]["local_path"]
        num_captions: int = int(config.get("num_captions", 5))

        with _pipeline_lock:
            pipeline = _load_pipeline()

        processor = pipeline["processor"]
        model = pipeline["model"]
        device = _get_device()

        raw_image = Image.open(image_path).convert("RGB")

        prompts = [
            "a detailed description of this image",
            "what is shown in this image?",
            "describe the main subject and setting",
            "a short caption for this image",
            "describe the style and composition",
        ]
        captions: list[str] = []
        for prompt in prompts[:num_captions]:
            inputs = processor(images=raw_image, return_tensors="pt").to(device)
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=128,
                    num_beams=5,
                    repetition_penalty=1.2,
                )
            caption = processor.decode(out[0], skip_special_tokens=True)
            caption = self._clean_caption(caption)
            if caption and caption not in captions:
                captions.append(caption)

        output_path = os.path.join(output_dir, "captions.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"suggestions": captions, "image_path": image_path}, f, ensure_ascii=False, indent=2)

        logger.info("BLIP-2: generated %d captions from %s", len(captions), image_path)
        return [{
            "local_path": output_path,
            "file_format": "json",
            "content_type": "application/json",
            "metadata": {"num_suggestions": len(captions)},
        }]

    def _clean_caption(self, text: str) -> str:
        text = text.strip()
        prefixes = ["a detailed description of this image:", "what is shown in this image?:",
                    "describe the main subject and setting:", "a short caption for this image:",
                    "describe the style and composition:", "this is "]
        for prefix in prefixes:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
        text = text.capitalize()
        if text and not text.endswith((".", "!", "?")):
            text += "."
        return text
