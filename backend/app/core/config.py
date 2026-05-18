"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_DEV_DIR = Path(__file__).resolve().parent.parent.parent / ".local_dev"


class Settings(BaseSettings):
    """Central configuration for the ArtPlatform backend.

    Values are read from a ``.env`` file located in the ``backend/`` directory,
    or from environment variables.  Environment variables take precedence.

    **LOCAL_DEV mode** — set ``LOCAL_DEV=true`` to run without Docker:
    - Database falls back to SQLite (aiosqlite) stored under ``backend/.local_dev/``
    - Object storage uses the local filesystem under ``backend/.local_dev/storage/``
    - Celery runs in solo pool (no Redis required)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Local Development ─────────────────────────────────────────────────
    LOCAL_DEV: bool = False

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://artplatform:artplatform@localhost:5432/artplatform"

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── MinIO / S3 ────────────────────────────────────────────────────────
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "artplatform"
    S3_REGION: str = "us-east-1"

    # ── Auth ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-to-a-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Celery ────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Application ───────────────────────────────────────────────────────
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Derived helpers ───────────────────────────────────────────────────

    @property
    def effective_database_url(self) -> str:
        """Return the DATABASE_URL, adjusted for LOCAL_DEV if needed."""
        if self.LOCAL_DEV:
            db_path = _LOCAL_DEV_DIR / "artplatform.db"
            return f"sqlite+aiosqlite:///{db_path}"
        return self.DATABASE_URL

    @property
    def local_dev_storage_dir(self) -> Path:
        """Return the root directory for local filesystem storage."""
        return _LOCAL_DEV_DIR / "storage"


def get_settings() -> Settings:
    """Return a cached *Settings* instance.

    Using a function keeps the import lightweight — no settings object is
    constructed at import time.
    """
    return Settings()
