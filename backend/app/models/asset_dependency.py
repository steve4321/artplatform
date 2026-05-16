from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_DEP_TYPES = (
    "references_texture",
    "references_material",
    "references_rig",
    "references_animation",
)


class AssetDependency(Base):
    __tablename__ = "asset_dependencies"
    __table_args__ = (
        CheckConstraint(
            f"dependency_type IN {repr(_DEP_TYPES)}",
            name="ck_asset_dependencies_type",
        ),
    )

    dependent_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dependency_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        Text, primary_key=True,
    )

    dependent_asset: Mapped["Asset"] = relationship(  # noqa: F821
        back_populates="dependencies",
        lazy="selectin",
        foreign_keys=[dependent_asset_id],
    )
    dependency_asset: Mapped["Asset"] = relationship(  # noqa: F821
        lazy="selectin",
        foreign_keys=[dependency_asset_id],
    )

    def __repr__(self) -> str:
        return (
            f"<AssetDependency {self.dependent_asset_id} "
            f"-> {self.dependency_asset_id} ({self.dependency_type})>"
        )
