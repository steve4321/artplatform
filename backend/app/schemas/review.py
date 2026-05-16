"""Pydantic schemas for the Review domain."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.user import UserBrief


class ReviewDecision(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"


class ReviewCreate(BaseModel):
    asset_id: UUID
    version: int
    decision: ReviewDecision
    notes: str | None = Field(default=None, max_length=5000)


class ReviewResponse(BaseModel):
    id: UUID
    asset_id: UUID
    version: int
    reviewer_id: UUID
    decision: str
    notes: str | None = None
    reviewed_at: datetime
    reviewer: UserBrief | None = None

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int
