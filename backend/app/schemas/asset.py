"""Pydantic schemas for the Asset domain (assets, versions, state transitions)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AssetType(str, enum.Enum):
    model_3d = "model_3d"
    texture_2d = "texture_2d"
    sprite = "sprite"
    material = "material"
    animation_clip = "animation_clip"
    animation = "animation_clip"  # alias for animation_clip
    prefab = "prefab"
    audio = "audio"
    vfx = "vfx"


class AssetSource(str, enum.Enum):
    ai_generated = "ai_generated"
    manual_upload = "manual_upload"
    hybrid = "hybrid"


class AssetState(str, enum.Enum):
    draft = "draft"
    processing = "processing"
    review = "review"
    approved = "approved"
    rejected = "rejected"
    published = "published"
    deprecated = "deprecated"


class VersionSourceType(str, enum.Enum):
    ai_pipeline = "ai_pipeline"
    manual_upload = "manual_upload"
    edited = "edited"


VALID_TRANSITIONS: dict[AssetState, set[AssetState]] = {
    AssetState.draft: {AssetState.processing, AssetState.review, AssetState.deprecated},
    AssetState.processing: {AssetState.draft, AssetState.review, AssetState.deprecated},
    AssetState.review: {AssetState.approved, AssetState.rejected, AssetState.draft, AssetState.deprecated},
    AssetState.approved: {AssetState.published, AssetState.deprecated},
    AssetState.rejected: {AssetState.draft, AssetState.deprecated},
    AssetState.published: {AssetState.deprecated},
    AssetState.deprecated: set(),
}


class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    asset_type: AssetType
    source: AssetSource = AssetSource.manual_upload
    tags: list[str] = Field(default_factory=list)
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = {"populate_by_name": True}


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    metadata_: dict[str, Any] | None = Field(default=None, alias="metadata")

    model_config = {"populate_by_name": True}


class AssetStateUpdate(BaseModel):
    state: AssetState

    @model_validator(mode="after")
    def _validate_transition(self) -> "AssetStateUpdate":
        return self

    @staticmethod
    def is_valid_transition(current: AssetState, target: AssetState) -> bool:
        return target in VALID_TRANSITIONS.get(current, set())


class UserBrief(BaseModel):
    id: UUID
    display_name: str
    email: str

    model_config = {"from_attributes": True}


class AssetVersionResponse(BaseModel):
    id: UUID
    asset_id: UUID
    version: int
    storage_key: str
    storage_key_thumbnail: str | None = None
    file_format: str
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None
    source_type: VersionSourceType
    pipeline_run_id: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetDependencyResponse(BaseModel):
    dependent_asset_id: UUID
    dependency_asset_id: UUID
    dependency_type: str

    model_config = {"from_attributes": True}


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    team_id: UUID
    name: str
    description: str
    asset_type: AssetType
    source: AssetSource
    state: AssetState
    current_version: int
    parent_asset_id: UUID | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata", validation_alias="metadata_")
    tags: list[str] = Field(default_factory=list)
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[AssetVersionResponse] = Field(default_factory=list)
    dependencies: list[AssetDependencyResponse] = Field(default_factory=list)
    created_by_user: UserBrief | None = None


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int
