from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class StageModeOption(BaseModel):
    mode: str
    label: str
    processor_name: str


class StageDefinition(BaseModel):
    stage: str
    label: str
    description: str
    modes: list[StageModeOption]
    cloud_providers: list[str]


class ProviderSettingUpdate(BaseModel):
    mode: str
    cloud_provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    extra_config: dict[str, Any] | None = None


class ProviderSettingResponse(BaseModel):
    id: UUID | None = None
    stage: str
    mode: str
    processor_name: str
    cloud_provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    extra_config: dict[str, Any] | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProviderSettingsListResponse(BaseModel):
    settings: list[ProviderSettingResponse]
    stage_definitions: list[StageDefinition]
