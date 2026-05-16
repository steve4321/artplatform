from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_SOURCE_TYPES = ("ai_pipeline", "manual_upload", "edited")


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (
        UniqueConstraint("asset_id", "version", name="uq_asset_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key_thumbnail: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    file_format: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    checksum_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        Text,
        CheckConstraint(
            f"source_type IN {repr(_SOURCE_TYPES)}",
            name="ck_asset_versions_source_type",
        ),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    asset: Mapped["Asset"] = relationship(  # noqa: F821
        back_populates="versions", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AssetVersion {self.id} v{self.version}>"
