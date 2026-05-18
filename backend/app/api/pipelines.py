"""Pipeline creation, status, and retry routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.storage import get_storage
from app.models import Asset, Artifact, PipelineRun, PipelineStep, User
from app.schemas.asset import AssetType
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineListResponse,
    PipelineResponse,
    PipelineStepResponse,
)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

PIPELINE_STAGES = [
    {"stage": "text_to_image", "processor_name": "sdxl"},
    {"stage": "image_to_3d", "processor_name": "tripo_sr"},
    {"stage": "mesh_cleanup", "processor_name": "instant_meshes"},
    {"stage": "uv_material", "processor_name": "xatlas_bpy"},
    {"stage": "rigging", "processor_name": "rigify"},
    {"stage": "animation", "processor_name": "hy_motion"},
]


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    payload: PipelineCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: User = Depends(get_current_user),
) -> PipelineResponse:
    """Create a new pipeline run and queue it for execution.

    If ``payload.asset_id`` is provided the pipeline is attached to that
    existing asset; otherwise a new asset is created in ``processing`` state.
    The actual Celery task execution is stubbed — only the DB records are
    created in this endpoint.
    """
    if payload.asset_id:
        stmt = select(Asset).where(Asset.id == payload.asset_id)
        result = await db.execute(stmt)
        asset = result.scalar_one_or_none()
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced asset not found",
            )
    else:
        asset = Asset(
            team_id=current_user.team_id,
            created_by=current_user.id,
            name=f"AI Generated — {payload.prompt[:80]}",
            description=payload.prompt,
            asset_type=AssetType.model_3d.value,
            source="ai_generated",
            state="processing",
            tags=[],
            metadata_={},
        )
        db.add(asset)
        await db.flush()

    config_dict = payload.config.model_dump()
    pipeline = PipelineRun(
        asset_id=asset.id,
        prompt=payload.prompt,
        reference_image_key=payload.reference_image_key,
        status="pending",
        config=config_dict,
        total_stages=len(PIPELINE_STAGES),
        completed_stages=0,
    )
    db.add(pipeline)
    await db.flush()

    for idx, stage_def in enumerate(PIPELINE_STAGES, start=1):
        stage_config = config_dict.get("stages", {}).get(stage_def["stage"], {})
        step = PipelineStep(
            pipeline_run_id=pipeline.id,
            stage_order=idx,
            stage=stage_def["stage"],
            processor_name=stage_config.get("processor_name", stage_def["processor_name"]),
            status="pending",
            config=stage_config.get("params", {}),
        )
        db.add(step)

    await db.commit()

    stmt = (
        select(PipelineRun)
        .where(PipelineRun.id == pipeline.id)
        .options(selectinload(PipelineRun.steps))
    )
    result = await db.execute(stmt)
    run = result.scalar_one()
    return PipelineResponse.model_validate(run)


@router.get("", response_model=PipelineListResponse)
async def list_pipelines(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    asset_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
) -> PipelineListResponse:
    """List pipeline runs with optional filtering."""
    base = select(PipelineRun).options(selectinload(PipelineRun.steps))
    count_stmt = select(func.count()).select_from(PipelineRun)

    if asset_id:
        base = base.where(PipelineRun.asset_id == asset_id)
        count_stmt = count_stmt.where(PipelineRun.asset_id == asset_id)
    if status_filter:
        base = base.where(PipelineRun.status == status_filter)
        count_stmt = count_stmt.where(PipelineRun.status == status_filter)

    total = (await db.execute(count_stmt)).scalar_one()
    offset = (page - 1) * page_size
    result = await db.execute(base.order_by(PipelineRun.created_at.desc()).offset(offset).limit(page_size))
    items = result.scalars().all()

    return PipelineListResponse(
        items=[PipelineResponse.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineResponse:
    """Retrieve a pipeline run with all its steps."""
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.id == pipeline_id)
        .options(selectinload(PipelineRun.steps))
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return PipelineResponse.model_validate(run)


@router.post("/{pipeline_id}/retry/{stage_order}", response_model=PipelineResponse)
async def retry_stage(
    pipeline_id: UUID,
    stage_order: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(require_role("admin", "artist")),
) -> PipelineResponse:
    """Retry a pipeline from a specific stage.

    Resets the target stage and all subsequent stages to ``pending``.
    """
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.id == pipeline_id)
        .options(selectinload(PipelineRun.steps))
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")

    target_found = False
    for step in sorted(run.steps, key=lambda s: s.stage_order):
        if step.stage_order >= stage_order:
            target_found = True
            step.status = "pending"
            step.error_message = None
            step.duration_ms = None
            step.started_at = None
            step.completed_at = None

    if not target_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stage order {stage_order} not found in this pipeline",
        )

    run.status = "running"
    await db.commit()

    stmt = (
        select(PipelineRun)
        .where(PipelineRun.id == pipeline_id)
        .options(selectinload(PipelineRun.steps))
    )
    result = await db.execute(stmt)
    run = result.scalar_one()
    return PipelineResponse.model_validate(run)


@router.get("/{pipeline_id}/steps/{stage_order}/output")
async def get_step_output(
    pipeline_id: UUID,
    stage_order: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Get a presigned download URL for an intermediate pipeline artifact."""
    stmt = select(PipelineStep).where(
        PipelineStep.pipeline_run_id == pipeline_id,
        PipelineStep.stage_order == stage_order,
    )
    result = await db.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")

    if not step.output_artifact_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No output artifact available for this step",
        )

    artifact_id = step.output_artifact_ids[0]
    art_result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = art_result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    storage = get_storage()
    url = storage.generate_presigned_url(artifact.storage_key)
    return {"url": url, "expires_in": "3600"}
