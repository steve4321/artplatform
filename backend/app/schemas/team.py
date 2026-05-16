"""Pydantic schemas for the Team domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class TeamResponse(BaseModel):
    id: UUID
    name: str
    settings: dict[str, Any] = Field(default_factory=dict)
    member_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TeamListResponse(BaseModel):
    items: list[TeamResponse]
    total: int
    page: int
    page_size: int
