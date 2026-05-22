from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_LINK_TYPES = (
    "edited_from",
    "replaces",
    "imported_from",
)


class AssetVersionLink(Base):
    __tablename__ = "asset_version_links"
    __table_args__ = (
        CheckConstraint(
            f"link_type IN {repr(_LINK_TYPES)}",
            name="ck_asset_version_links_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    from_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    link_type: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    from_version: Mapped["AssetVersion"] = relationship(  # noqa: F821
        foreign_keys=[from_version_id],
        lazy="selectin",
    )
    to_version: Mapped["AssetVersion"] = relationship(  # noqa: F821
        foreign_keys=[to_version_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AssetVersionLink {self.id} "
            f"{self.from_version_id} -> {self.to_version_id} "
            f"({self.link_type})>"
        )
