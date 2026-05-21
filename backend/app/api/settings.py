"""Provider settings — configure mock/local/cloud mode per pipeline stage."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.models.provider_setting import ProviderSetting
from app.pipeline.pipeline_configs import (
    STAGE_DEFINITIONS,
    get_processor_name_for_mode,
)
from app.schemas.provider_setting import (
    ProviderSettingResponse,
    ProviderSettingsListResponse,
    ProviderSettingUpdate,
    StageDefinition,
    StageModeOption,
)

router = APIRouter(prefix="/settings", tags=["settings"])


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

    settings_by_stage = {s.stage: s for s in settings}

    response_settings = []
    for sd in STAGE_DEFINITIONS:
        existing = settings_by_stage.get(sd["stage"])
        if existing:
            resp = ProviderSettingResponse.model_validate(existing)
            resp.api_key = _mask_api_key(existing.api_key)
            response_settings.append(resp)
        else:
            default_processor = sd["modes"][0]["processor_name"]
            response_settings.append(ProviderSettingResponse(
                id=None,
                stage=sd["stage"],
                mode=sd["modes"][0]["mode"],
                processor_name=default_processor,
                cloud_provider=None,
                api_key=None,
                base_url=None,
                extra_config=None,
                updated_at=None,
            ))

    stage_defs = [
        StageDefinition(
            stage=sd["stage"],
            label=sd["label"],
            description=sd["description"],
            modes=[StageModeOption(**m) for m in sd["modes"]],
            cloud_providers=sd["cloud_providers"],
        )
        for sd in STAGE_DEFINITIONS
    ]

    return ProviderSettingsListResponse(
        settings=response_settings,
        stage_definitions=stage_defs,
    )


@router.put("/providers/{stage}", response_model=ProviderSettingResponse)
async def update_provider_setting(
    stage: str,
    payload: ProviderSettingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: User = Depends(get_current_user),
) -> ProviderSettingResponse:
    stage_def = None
    for sd in STAGE_DEFINITIONS:
        if sd["stage"] == stage:
            stage_def = sd
            break
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
        select(ProviderSetting).where(ProviderSetting.stage == stage)
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
