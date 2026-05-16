"""CRUD + version management routes for assets."""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.storage import get_storage
from app.models import Asset, AssetVersion, User
from app.schemas.asset import (
    AssetCreate,
    AssetListResponse,
    AssetResponse,
    AssetState,
    AssetStateUpdate,
    AssetType,
    AssetUpdate,
    AssetVersionResponse,
)

router = APIRouter(prefix="/assets", tags=["assets"])

DEFAULT_TEAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _get_user_id() -> UUID:
    return DEFAULT_USER_ID


async def _load_asset_or_404(db: AsyncSession, asset_id: UUID) -> Asset:
    stmt = (
        select(Asset)
        .where(Asset.id == asset_id)
        .options(
            selectinload(Asset.versions),
            selectinload(Asset.dependencies),
            selectinload(Asset.created_by_user),
        )
    )
    result = await db.execute(stmt)
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.get("", response_model=AssetListResponse)
async def list_assets(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: AssetState | None = None,
    asset_type: AssetType | None = None,
    source: str | None = None,
    tags: str | None = Query(None, description="Comma-separated tag list"),
    search: str | None = Query(None, description="Search by name (ILIKE)"),
) -> AssetListResponse:
    """List assets with optional filtering and pagination."""
    base = select(Asset).options(
        selectinload(Asset.versions),
        selectinload(Asset.dependencies),
        selectinload(Asset.created_by_user),
    )
    count_stmt = select(func.count()).select_from(Asset)

    if state is not None:
        base = base.where(Asset.state == state.value)
        count_stmt = count_stmt.where(Asset.state == state.value)
    if asset_type is not None:
        base = base.where(Asset.asset_type == asset_type.value)
        count_stmt = count_stmt.where(Asset.asset_type == asset_type.value)
    if source is not None:
        base = base.where(Asset.source == source)
        count_stmt = count_stmt.where(Asset.source == source)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        base = base.where(Asset.tags.contains(tag_list))
        count_stmt = count_stmt.where(Asset.tags.contains(tag_list))
    if search:
        base = base.where(Asset.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(Asset.name.ilike(f"%{search}%"))

    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base.order_by(Asset.created_at.desc()).offset(offset).limit(page_size)
    )
    items = items_result.scalars().all()

    return AssetListResponse(
        items=[AssetResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """Create a new asset."""
    asset = Asset(
        team_id=DEFAULT_TEAM_ID,
        created_by=_get_user_id(),
        name=payload.name,
        description=payload.description,
        asset_type=payload.asset_type.value,
        source=payload.source.value,
        state=AssetState.draft.value,
        tags=payload.tags,
        metadata_=payload.metadata_,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    asset = await _load_asset_or_404(db, asset.id)
    return AssetResponse.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """Retrieve a single asset by ID with versions and dependencies."""
    asset = await _load_asset_or_404(db, asset_id)
    return AssetResponse.model_validate(asset)


@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: UUID,
    payload: AssetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """Partially update an asset."""
    asset = await _load_asset_or_404(db, asset_id)
    update_data = payload.model_dump(exclude_unset=True, by_alias=False)
    for field, value in update_data.items():
        setattr(asset, field, value)
    await db.commit()
    await db.refresh(asset)
    asset = await _load_asset_or_404(db, asset.id)
    return AssetResponse.model_validate(asset)


@router.patch("/{asset_id}/state", response_model=AssetResponse)
async def transition_state(
    asset_id: UUID,
    payload: AssetStateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetResponse:
    """Transition an asset to a new lifecycle state.

    Validates the transition is allowed by the state machine before applying.
    """
    asset = await _load_asset_or_404(db, asset_id)
    current = AssetState(asset.state)
    target = payload.state

    if not AssetStateUpdate.is_valid_transition(current, target):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: {current.value} -> {target.value}",
        )

    asset.state = target.value
    await db.commit()
    await db.refresh(asset)
    asset = await _load_asset_or_404(db, asset.id)
    return AssetResponse.model_validate(asset)


@router.post(
    "/{asset_id}/versions",
    response_model=AssetVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_version(
    asset_id: UUID,
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    source_type: str = "manual_upload",
) -> AssetVersionResponse:
    """Upload a new file version for an asset.

    Streams the file to MinIO without buffering the entire payload in memory.
    Computes SHA-256 checksum during upload for integrity verification.
    """
    asset = await _load_asset_or_404(db, asset_id)

    version_number = asset.current_version + 1
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    storage_key = f"assets/{asset_id}/v{version_number}/{uuid.uuid4()}.{ext}"

    storage = get_storage()
    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()
    storage.upload_file(storage_key, content, file.content_type or "application/octet-stream")

    version = AssetVersion(
        asset_id=asset_id,
        version=version_number,
        storage_key=storage_key,
        file_format=ext,
        file_size_bytes=len(content),
        checksum_sha256=checksum,
        source_type=source_type,
    )
    db.add(version)

    asset.current_version = version_number
    await db.commit()
    await db.refresh(version)
    return AssetVersionResponse.model_validate(version)


@router.get("/{asset_id}/versions/{version}/download")
async def download_version(
    asset_id: UUID,
    version: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Get a presigned download URL for a specific asset version."""
    stmt = select(AssetVersion).where(
        AssetVersion.asset_id == asset_id,
        AssetVersion.version == version,
    )
    result = await db.execute(stmt)
    ver = result.scalar_one_or_none()
    if ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    storage = get_storage()
    url = storage.generate_presigned_url(ver.storage_key)
    return {"url": url, "expires_in": "3600"}


@router.delete("/{asset_id}", response_model=AssetResponse)
async def deprecate_asset(
    asset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(require_role("admin")),
) -> AssetResponse:
    """Soft-delete an asset by setting state to deprecated."""
    asset = await _load_asset_or_404(db, asset_id)
    current = AssetState(asset.state)
    if current == AssetState.deprecated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset is already deprecated",
        )
    asset.state = AssetState.deprecated.value
    await db.commit()
    await db.refresh(asset)
    asset = await _load_asset_or_404(db, asset.id)
    return AssetResponse.model_validate(asset)


# ── Export routes ─────────────────────────────────────────────────────────


@router.get("/{asset_id}/export/unity")
async def export_unity(
    asset_id: UUID,
    version: int = Query(..., description="Asset version to export"),
    db: Annotated[AsyncSession, Depends(get_db)] = ...,
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    from app.services.export_service import ExportService

    svc = ExportService()
    try:
        url = await svc.export_as_unity_package(asset_id, version, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"url": url, "format": "unity_zip"}


@router.get("/{asset_id}/export/glb")
async def export_glb(
    asset_id: UUID,
    version: int = Query(..., description="Asset version to export"),
    db: Annotated[AsyncSession, Depends(get_db)] = ...,
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    from app.services.export_service import ExportService

    svc = ExportService()
    try:
        url = await svc.export_as_glb(asset_id, version, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"url": url, "format": "glb"}


@router.get("/{asset_id}/export/fbx")
async def export_fbx(
    asset_id: UUID,
    version: int = Query(..., description="Asset version to export"),
    db: Annotated[AsyncSession, Depends(get_db)] = ...,
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    from app.services.export_service import ExportService

    svc = ExportService()
    try:
        url = await svc.export_as_fbx(asset_id, version, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"url": url, "format": "fbx"}
