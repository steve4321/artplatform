"""Seed default data for LOCAL_DEV mode."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import hash_password
from app.core.config import get_settings
from app.models import Team, User

DEFAULT_TEAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_ADMIN_EMAIL = "admin@artplatform.local"
DEFAULT_ADMIN_PASSWORD = "admin123456"


async def seed_default_data() -> None:
    """Create default team and admin user if they don't exist (LOCAL_DEV only)."""
    settings = get_settings()
    if not settings.LOCAL_DEV:
        return

    from app.core.database import _get_engine, _get_session_factory

    _get_engine()
    factory = _get_session_factory()

    async with factory() as session:
        result = await session.execute(select(Team).where(Team.id == DEFAULT_TEAM_ID))
        team = result.scalar_one_or_none()
        if team is None:
            team = Team(id=DEFAULT_TEAM_ID, name="Default Team")
            session.add(team)

        result = await session.execute(select(User).where(User.email == DEFAULT_ADMIN_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                id=DEFAULT_ADMIN_ID,
                email=DEFAULT_ADMIN_EMAIL,
                hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
                display_name="Admin",
                role="admin",
                team_id=DEFAULT_TEAM_ID,
                is_active=True,
            )
            session.add(user)

        await session.commit()
