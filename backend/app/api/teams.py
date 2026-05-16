"""Team management routes."""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Team, User
from app.schemas.team import TeamCreate, TeamListResponse, TeamResponse

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=TeamListResponse)
async def list_teams(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> TeamListResponse:
    """List all teams with pagination."""
    count_stmt = select(func.count()).select_from(Team)
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Team).order_by(Team.name).offset(offset).limit(page_size)
    )
    teams = result.scalars().all()

    items = []
    for team in teams:
        member_count = (
            await db.execute(
                select(func.count()).select_from(User).where(User.team_id == team.id)
            )
        ).scalar_one()
        items.append(
            TeamResponse(
                id=team.id,
                name=team.name,
                settings=team.settings,
                member_count=member_count,
                created_at=team.created_at,
            )
        )

    return TeamListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    """Create a new team."""
    team = Team(name=payload.name)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return TeamResponse(
        id=team.id,
        name=team.name,
        settings=team.settings,
        member_count=0,
        created_at=team.created_at,
    )


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    """Retrieve a team by ID."""
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    member_count = (
        await db.execute(
            select(func.count()).select_from(User).where(User.team_id == team.id)
        )
    ).scalar_one()

    return TeamResponse(
        id=team.id,
        name=team.name,
        settings=team.settings,
        member_count=member_count,
        created_at=team.created_at,
    )
