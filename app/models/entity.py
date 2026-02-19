from sqlalchemy import Column, DateTime, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class Entity(Base):
    """
    Canonical entity lookup table.

    Stores unique (name, type) pairs extracted by GCP NL annotateText.
    Entities are deduplicated: "Google" + "ORGANIZATION" appears once,
    regardless of how many articles reference it.
    """

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    wikipedia_url = Column(String(1000), nullable=True)
    mid = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # M2M relationship via association table
    article_entities = relationship(
        "ArticleEntity",
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_entities_name_type", "name", "type", unique=True),
        Index("ix_entities_name", "name"),
        Index("ix_entities_type", "type"),
    )
