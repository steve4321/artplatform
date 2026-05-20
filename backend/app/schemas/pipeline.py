"""Pydantic schemas for the Pipeline domain.

Covers pipeline runs, pipeline steps, and pipeline configuration.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PipelineStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    partial = "partial"
    failed = "failed"


class StepStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"



class StageConfig(BaseModel):
    processor_name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    stages: dict[str, StageConfig] = Field(default_factory=dict)


class PipelineCreate(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    reference_image_key: str | None = None
    config: PipelineConfig = Field(default_factory=PipelineConfig)
    asset_id: UUID | None = None
    pipeline_type: str = Field(default="3d_art", pattern=r"^(3d_scene|3d_character|3d_art|2d_art)$")


class PipelineStepResponse(BaseModel):
    id: UUID
    pipeline_run_id: UUID
    stage_order: int
    stage: str
    processor_name: str
    status: StepStatus
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("input_artifact_ids", "output_artifact_ids", mode="before")
    @classmethod
    def _coerce_json_default(cls, v: Any) -> list:
        if isinstance(v, dict):
            return []
        if v is None:
            return []
        return list(v)


class PipelineResponse(BaseModel):
    id: UUID
    asset_id: UUID
    prompt: str
    reference_image_key: str | None = None
    status: PipelineStatus
    config: dict[str, Any] = Field(default_factory=dict)
    total_stages: int | None = None
    completed_stages: int = 0
    created_at: datetime
    completed_at: datetime | None = None
    steps: list[PipelineStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PipelineListResponse(BaseModel):
    items: list[PipelineResponse]
    total: int
    page: int
    page_size: int
