"""Async SQLAlchemy engine, session factory, and declarative base."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


def _set_sqlite_wal(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Import this in every models module so Alembic can discover your tables.
    """


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _get_engine():
    """Lazily create the async engine (singleton)."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        settings = get_settings()
        url = settings.effective_database_url

        if _is_sqlite(url):
            db_path = Path(url.split("///")[-1])
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _engine = create_async_engine(
                url,
                echo=settings.DEBUG,
                connect_args={"check_same_thread": False},
            )
            event.listen(_engine.sync_engine, "connect", _set_sqlite_wal)
        else:
            _engine = create_async_engine(
                url,
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
