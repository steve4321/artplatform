"""Pydantic schemas for the User domain."""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserRole(str, enum.Enum):
    admin = "admin"
    artist = "artist"
    reviewer = "reviewer"
    viewer = "viewer"


class UserCreate(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.artist
    team_id: UUID | None = None


class UserResponse(BaseModel):
    id: UUID
    team_id: UUID | None = None
    email: str
    display_name: str
    role: str
    is_active: bool = True
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserBrief(BaseModel):
    id: UUID
    display_name: str
    email: str

    model_config = {"from_attributes": True}
