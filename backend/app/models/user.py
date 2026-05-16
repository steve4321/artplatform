from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

_VALID_ROLES = ("admin", "artist", "reviewer", "viewer")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"role IN {repr(_VALID_ROLES)}",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default="true", default=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()")

    team: Mapped["Team | None"] = relationship(  # noqa: F821
        back_populates="users", lazy="selectin",
    )
    created_assets: Mapped[list["Asset"]] = relationship(  # noqa: F821
        back_populates="creator",
        lazy="selectin",
        foreign_keys="[Asset.created_by]",
    )
    reviews: Mapped[list["Review"]] = relationship(  # noqa: F821
        back_populates="reviewer", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email!r}>"
