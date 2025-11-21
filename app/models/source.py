from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class Source(Base):
    """News source model - represents Mediastack source identifiers."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)

    # Core source information (what Mediastack provides)
    name = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,  # Index for source lookups
        comment="Mediastack source identifier (e.g., 'bbc', 'cnn', 'independent')",
    )

    # Audit fields (best practice)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the source was added to our system",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="When the source was last updated",
    )

    # Relationships
    articles = relationship(
        "Article",
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id!r} name={self.name!r} domain={self.domain!r}>"
