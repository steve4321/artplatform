from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="team", lazy="selectin",
    )
    assets: Mapped[list["Asset"]] = relationship(  # noqa: F821
        back_populates="team", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Team {self.id} {self.name!r}>"
