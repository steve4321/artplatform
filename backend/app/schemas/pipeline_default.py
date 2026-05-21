from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PipelineDefaultUpdate(BaseModel):
    pipeline_type: str
    default_mode: str


class PipelineDefaultResponse(BaseModel):
    pipeline_type: str
    default_mode: str
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
