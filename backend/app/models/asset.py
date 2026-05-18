from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_ASSET_TYPES = (
    "model_3d", "texture_2d", "sprite", "material",
    "animation_clip", "prefab", "audio", "vfx",
)
_SOURCE_TYPES = ("ai_generated", "manual_upload", "hybrid")
_STATES = (
    "draft", "processing", "review", "approved",
    "rejected", "published", "deprecated",
)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            f"asset_type IN {repr(_ASSET_TYPES)}",
            name="ck_assets_asset_type",
        ),
        CheckConstraint(
            f"source IN {repr(_SOURCE_TYPES)}",
            name="ck_assets_source",
        ),
        CheckConstraint(
            f"state IN {repr(_STATES)}",
            name="ck_assets_state",
        ),
        Index("idx_assets_team_state", "team_id", "state"),
        Index("idx_assets_parent", "parent_asset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'"),
    )
    current_version: Mapped[int] = mapped_column(
        Integer, server_default="1", default=1,
    )
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSON, server_default=text("'{}'"),
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON, server_default=text("'{}'"),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=datetime.utcnow,
    )

    team: Mapped["Team"] = relationship(  # noqa: F821
        back_populates="assets", lazy="selectin",
    )
    creator: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="created_assets",
        lazy="selectin",
        foreign_keys=[created_by],
    )
    versions: Mapped[list["AssetVersion"]] = relationship(  # noqa: F821
        back_populates="asset",
        lazy="selectin",
        order_by="[AssetVersion.version]",
    )
    dependencies: Mapped[list["AssetDependency"]] = relationship(  # noqa: F821
        back_populates="dependent_asset",
        lazy="selectin",
        foreign_keys="[AssetDependency.dependent_asset_id]",
    )
    pipeline_runs: Mapped[list["PipelineRun"]] = relationship(  # noqa: F821
        back_populates="asset", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Asset {self.id} {self.name!r} v{self.current_version}>"
