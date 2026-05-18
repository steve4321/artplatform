"""Image-to-prompt API — generate prompt suggestions from a reference image."""

from __future__ import annotations

import json
import tempfile
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

router = APIRouter(prefix="/prompts", tags=["prompts"])

IMAGE_FORMATS = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_SIZE_MB = 10


class PromptSuggestionsResponse(BaseModel):
    suggestions: list[str]


@router.post("/generate-from-image", response_model=PromptSuggestionsResponse)
async def generate_prompts_from_image(
    file: UploadFile = File(...),
) -> PromptSuggestionsResponse:
    """Upload a reference image to get prompt suggestions.

    Uses BLIP-2 to generate 3-5 basic prompt suggestions.
    The user can pick one, edit it, and use it in the generation pipeline.
    """
    if file.size is not None and file.size > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image too large (max {MAX_SIZE_MB}MB)",
        )

    content_type = file.content_type or ""
    if content_type.lower() not in IMAGE_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported formats: PNG, JPG, WebP",
        )

    suffix = ".png" if "png" in content_type else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        from app.workers.stage_processors.image_captioning import ImageCaptioningBLIP2

        processor = ImageCaptioningBLIP2()
        can_run = processor.can_run(
            [{"local_path": tmp_path, "file_format": suffix.lstrip(".")}],
            {"num_captions": 5},
        )
        if not can_run:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not process this image",
            )

        with tempfile.TemporaryDirectory() as output_dir:
            artifacts = processor.run(
                [{"local_path": tmp_path, "file_format": suffix.lstrip(".")}],
                {"num_captions": 5},
                output_dir,
            )

        if not artifacts:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Captioning produced no output",
            )

        with open(artifacts[0]["local_path"]) as f:
            data = json.load(f)

        suggestions = data.get("suggestions", [])
        if not suggestions:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No captions generated",
            )

        return PromptSuggestionsResponse(suggestions=suggestions)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Captioning failed: {exc}",
        )
    finally:
        import os
        os.unlink(tmp_path)
