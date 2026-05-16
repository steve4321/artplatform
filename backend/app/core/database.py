"""Async SQLAlchemy engine, session factory, and declarative base."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Import this in every models module so Alembic can discover your tables.
    """


def _get_engine():
    """Lazily create the async engine (singleton)."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazily create the session factory (singleton)."""
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically closed when the request finishes.
    """
    factory = _get_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Prepare the engine & session factory (call at app startup)."""
    _get_engine()
    _get_session_factory()


async def close_db() -> None:
    """Dispose of the engine (call at app shutdown)."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
