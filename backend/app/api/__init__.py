"""API router aggregation."""

from fastapi import APIRouter

from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.pipelines import router as pipelines_router
from app.api.prompts import router as prompts_router
from app.api.reviews import router as reviews_router
from app.api.teams import router as teams_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(assets_router)
api_router.include_router(auth_router)
api_router.include_router(pipelines_router)
api_router.include_router(prompts_router)
api_router.include_router(reviews_router)
api_router.include_router(teams_router)


@api_router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
