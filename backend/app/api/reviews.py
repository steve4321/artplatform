"""Review submission and listing routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Asset, AssetVersion, Review, User
from app.schemas.review import ReviewCreate, ReviewListResponse, ReviewResponse

router = APIRouter(tags=["reviews"])


@router.post(
    "/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_review(
    payload: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
) -> ReviewResponse:
    """Submit a review for an asset version.

    When approved: the version status becomes active and becomes the
    asset's current version.
    When rejected: the version status becomes rejected.
    """
    stmt = select(Asset).where(Asset.id == payload.asset_id)
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    version_stmt = select(AssetVersion).where(
        AssetVersion.asset_id == payload.asset_id,
        AssetVersion.version == payload.version,
    )
    version_result = await db.execute(version_stmt)
    version = version_result.scalar_one_or_none()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {payload.version} does not exist for this asset",
        )

    if payload.decision.value == "approved":
        version.status = "active"
        if payload.version > asset.current_version:
            asset.current_version = payload.version
    elif payload.decision.value == "rejected":
        version.status = "rejected"

    review = Review(
        asset_id=payload.asset_id,
        version=payload.version,
        reviewer_id=current_user.id,
        decision=payload.decision.value,
        notes=payload.notes,
    )
    db.add(review)
    await db.commit()

    stmt = (
        select(Review)
        .where(Review.id == review.id)
        .options(selectinload(Review.reviewer))
    )
    result = await db.execute(stmt)
    review = result.scalar_one()
    return ReviewResponse.model_validate(review)


@router.get(
    "/assets/{asset_id}/reviews",
    response_model=ReviewListResponse,
)
async def list_asset_reviews(
    asset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReviewListResponse:
    """List all reviews for a given asset with pagination."""
    stmt_asset = select(Asset).where(Asset.id == asset_id)
    asset_result = await db.execute(stmt_asset)
    if asset_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    base = (
        select(Review)
        .where(Review.asset_id == asset_id)
        .options(selectinload(Review.reviewer))
    )
    count_stmt = select(func.count()).select_from(Review).where(Review.asset_id == asset_id)

    total = (await db.execute(count_stmt)).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Review.reviewed_at.desc()).offset(offset).limit(page_size)
    )
    items = result.scalars().all()

    return ReviewListResponse(
        items=[ReviewResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )
