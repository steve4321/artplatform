"""Shared test fixtures for ArtPlatform backend tests."""

import os

# Force LOCAL_DEV before any app imports
os.environ["LOCAL_DEV"] = "true"

import asyncio
import shutil
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, _get_engine, close_db, init_db
from app.core.seed import DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD, seed_default_data
from app.core.storage import init_storage

_LOCAL_DEV_DIR = Path(__file__).resolve().parent.parent / ".local_dev"


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_app():
    """Bootstrap the full app: DB, storage, seed data — once per session."""
    # Ensure .local_dev directory exists
    _LOCAL_DEV_DIR.mkdir(parents=True, exist_ok=True)

    await init_db()

    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await init_storage()
    await seed_default_data()

    yield

    await close_db()
    # Clean up .local_dev after tests
    if _LOCAL_DEV_DIR.exists():
        shutil.rmtree(_LOCAL_DEV_DIR, ignore_errors=True)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired to the FastAPI app via ASGI transport."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """Return Authorization headers for the default admin user."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": DEFAULT_ADMIN_EMAIL, "password": DEFAULT_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
