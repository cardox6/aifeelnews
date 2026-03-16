from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article_entity import ArticleEntity


class Entity(Base):
    """
    Canonical entity lookup table.

    Stores unique (name, type) pairs extracted by GCP NL annotateText.
    Entities are deduplicated: "Google" + "ORGANIZATION" appears once,
    regardless of how many articles reference it.
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(50))
    wikipedia_url: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    mid: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # M2M relationship via association table
    article_entities: Mapped[List["ArticleEntity"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_entities_name_type", "name", "type", unique=True),
        Index("ix_entities_name", "name"),
        Index("ix_entities_type", "type"),
    )
