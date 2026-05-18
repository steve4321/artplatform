"""FastAPI application factory with lifespan management."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.seed import seed_default_data
from app.core.storage import init_storage


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of external service connections."""
    await init_db()
    await init_storage()
    await seed_default_data()
    yield
    await close_db()


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="ArtPlatform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from app.api import api_router
    app.include_router(api_router)

    return app


app = create_app()
