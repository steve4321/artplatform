"""Provider settings — configure mock/local/cloud mode per pipeline stage."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models.pipeline_default import PipelineDefault
from app.models.provider_setting import ProviderSetting
from app.pipeline.pipeline_configs import (
    STAGE_DEFINITIONS,
    get_processor_name_for_mode,
    get_stage_definition,
)
from app.schemas.pipeline_default import (
    PipelineDefaultResponse,
    PipelineDefaultUpdate,
)
from app.schemas.provider_setting import (
    PipelineTypeStageDefinitions,
    ProviderSettingResponse,
    ProviderSettingsListResponse,
    ProviderSettingUpdate,
    StageDefinition,
    StageModeOption,
)

router = APIRouter(prefix="/settings", tags=["settings"])

PIPELINE_TYPE_LABELS = {
    "3d_scene": "3D 场景管线",
    "3d_character": "3D 角色管线",
    "2d_art": "2D 管线",
}


def _mask_api_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]


@router.get("/providers", response_model=ProviderSettingsListResponse)
async def list_provider_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
) -> ProviderSettingsListResponse:
    result = await db.execute(select(ProviderSetting))
    settings = result.scalars().all()

    settings_by_key: dict[tuple[str, str], ProviderSetting] = {}
    for s in settings:
        settings_by_key[(s.pipeline_type, s.stage)] = s

    defaults_result = await db.execute(select(PipelineDefault))
    pipeline_defaults = {pd.pipeline_type: pd.default_mode for pd in defaults_result.scalars().all()}

    response_settings: list[ProviderSettingResponse] = []
    stage_defs_list: list[PipelineTypeStageDefinitions] = []

    for pipeline_type, stage_defs in STAGE_DEFINITIONS.items():
        stage_def_models = []
        for sd in stage_defs:
            existing = settings_by_key.get((pipeline_type, sd["stage"]))
            if existing:
                resp = ProviderSettingResponse.model_validate(existing)
                resp.api_key = _mask_api_key(existing.api_key)
                response_settings.append(resp)
            else:
                default_processor = sd["modes"][0]["processor_name"]
                response_settings.append(ProviderSettingResponse(
                    id=None,
                    pipeline_type=pipeline_type,
                    stage=sd["stage"],
                    mode=sd["modes"][0]["mode"],
                    processor_name=default_processor,
                    cloud_provider=None,
                    api_key=None,
                    base_url=None,
                    extra_config=None,
                    updated_at=None,
                ))

            stage_def_models.append(StageDefinition(
                stage=sd["stage"],
                label=sd["label"],
                description=sd["description"],
                modes=[StageModeOption(**m) for m in sd["modes"]],
                cloud_providers=sd["cloud_providers"],
            ))

        stage_defs_list.append(PipelineTypeStageDefinitions(
            pipeline_type=pipeline_type,
            label=PIPELINE_TYPE_LABELS.get(pipeline_type, pipeline_type),
            stages=stage_def_models,
        ))

    return ProviderSettingsListResponse(
        settings=response_settings,
        defaults=pipeline_defaults,
        stage_definitions=stage_defs_list,
    )


@router.put("/providers/{pipeline_type}/{stage}", response_model=ProviderSettingResponse)
async def update_provider_setting(
    pipeline_type: str,
    stage: str,
    payload: ProviderSettingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
) -> ProviderSettingResponse:
    if pipeline_type not in STAGE_DEFINITIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown pipeline_type: {pipeline_type}",
        )

    stage_def = get_stage_definition(stage)
    if stage_def is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown stage: {stage}",
        )

    valid_modes = [m["mode"] for m in stage_def["modes"]]
    if payload.mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid mode '{payload.mode}' for stage "
                f"'{stage}'. Valid: {valid_modes}"
            ),
        )

    if payload.mode == "cloud":
        if not payload.cloud_provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cloud_provider is required when mode is 'cloud'",
            )
        if payload.cloud_provider not in stage_def["cloud_providers"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid cloud_provider '{payload.cloud_provider}'. "
                    f"Valid: {stage_def['cloud_providers']}"
                ),
            )

    result = await db.execute(
        select(ProviderSetting).where(
            ProviderSetting.pipeline_type == pipeline_type,
            ProviderSetting.stage == stage,
        )
    )
    setting = result.scalar_one_or_none()

    processor_name = get_processor_name_for_mode(stage, payload.mode)

    if setting:
        setting.mode = payload.mode
        setting.processor_name = processor_name
        setting.cloud_provider = payload.cloud_provider if payload.mode == "cloud" else None
        if payload.api_key:
            setting.api_key = payload.api_key
        elif payload.mode != "cloud":
            setting.api_key = None
        setting.base_url = payload.base_url if payload.mode == "cloud" else None
        setting.extra_config = payload.extra_config
    else:
        setting = ProviderSetting(
            pipeline_type=pipeline_type,
            stage=stage,
            mode=payload.mode,
            processor_name=processor_name,
            cloud_provider=payload.cloud_provider if payload.mode == "cloud" else None,
            api_key=payload.api_key if payload.mode == "cloud" else None,
            base_url=payload.base_url if payload.mode == "cloud" else None,
            extra_config=payload.extra_config,
        )
        db.add(setting)

    await db.commit()
    await db.refresh(setting)

    resp = ProviderSettingResponse.model_validate(setting)
    resp.api_key = _mask_api_key(setting.api_key)
    return resp


@router.get("/providers/defaults", response_model=list[PipelineDefaultResponse])
async def list_pipeline_defaults(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
) -> list[PipelineDefaultResponse]:
    result = await db.execute(select(PipelineDefault))
    return [PipelineDefaultResponse.model_validate(pd) for pd in result.scalars().all()]


@router.put("/providers/defaults", response_model=PipelineDefaultResponse)
async def update_pipeline_default(
    payload: PipelineDefaultUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
) -> PipelineDefaultResponse:
    if payload.pipeline_type not in STAGE_DEFINITIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown pipeline_type: {payload.pipeline_type}",
        )

    if payload.default_mode not in ("mock", "local", "cloud", "custom"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid default_mode: {payload.default_mode}",
        )

    old_result = await db.execute(
        select(PipelineDefault).where(PipelineDefault.pipeline_type == payload.pipeline_type)
    )
    old_default = old_result.scalar_one_or_none()

    from sqlalchemy import delete as sa_delete
    if (
        old_default
        and old_default.default_mode == "custom"
        and payload.default_mode != "custom"
    ):
        await db.execute(
            sa_delete(ProviderSetting).where(
                ProviderSetting.pipeline_type == payload.pipeline_type
            )
        )

    if old_default:
        old_default.default_mode = payload.default_mode
    else:
        old_default = PipelineDefault(
            pipeline_type=payload.pipeline_type,
            default_mode=payload.default_mode,
        )
        db.add(old_default)

    await db.commit()
    await db.refresh(old_default)
    return PipelineDefaultResponse.model_validate(old_default)
