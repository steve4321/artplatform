from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_RUN_STATUSES = ("pending", "running", "paused", "completed", "partial", "failed")
_STEP_STATUSES = ("pending", "running", "completed", "failed", "skipped")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {repr(_RUN_STATUSES)}",
            name="ck_pipeline_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    reference_image_key: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_stages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_stages: Mapped[int] = mapped_column(
        Integer, server_default="0", default=0,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    asset: Mapped["Asset"] = relationship(  # noqa: F821
        back_populates="pipeline_runs", lazy="selectin",
    )
    steps: Mapped[list["PipelineStep"]] = relationship(
        back_populates="pipeline_run",
        lazy="selectin",
        order_by="[PipelineStep.stage_order]",
    )

    def __repr__(self) -> str:
        return f"<PipelineRun {self.id} status={self.status!r}>"


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (
        CheckConstraint(
            f"status IN {repr(_STEP_STATUSES)}",
            name="ck_pipeline_steps_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    processor_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'"),
    )
    input_artifact_ids: Mapped[list[str]] = mapped_column(
        JSON, server_default=text("'{}'"),
    )
    output_artifact_ids: Mapped[list[str]] = mapped_column(
        JSON, server_default=text("'{}'"),
    )
    config: Mapped[dict | None] = mapped_column(
        JSON, server_default=text("'{}'"),
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    pipeline_run: Mapped["PipelineRun"] = relationship(
        back_populates="steps", lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineStep {self.id} "
            f"stage={self.stage!r} order={self.stage_order}>"
        )
