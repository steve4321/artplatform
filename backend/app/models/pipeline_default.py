"""PipelineDefault — default mode per pipeline type."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PipelineDefault(Base):
    __tablename__ = "pipeline_defaults"

    pipeline_type: Mapped[str] = mapped_column(Text, primary_key=True)
    default_mode: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
