from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_DECISIONS = ("approved", "rejected", "changes_requested")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            f"decision IN {repr(_DECISIONS)}",
            name="ck_reviews_decision",
        ),
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
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(server_default="now()")

    asset: Mapped["Asset"] = relationship(  # noqa: F821
        lazy="selectin",
    )
    reviewer: Mapped["User"] = relationship(  # noqa: F821
        back_populates="reviews", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Review {self.id} decision={self.decision!r}>"
