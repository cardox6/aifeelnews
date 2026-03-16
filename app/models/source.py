from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article


class Source(Base):
    """News source model - represents Mediastack source identifiers."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        comment="Mediastack source identifier (e.g., 'bbc', 'cnn', 'independent')",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        comment="When the source was added to our system",
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        comment="When the source was last updated",
    )

    # Relationships
    articles: Mapped[List["Article"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id!r} name={self.name!r}>"
