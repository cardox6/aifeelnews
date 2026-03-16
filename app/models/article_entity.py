from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.entity import Entity


class ArticleEntity(Base):
    """
    Association table for the Article <-> Entity M2M relationship.

    Each row represents one entity mention within one article,
    storing the article-specific salience score from GCP NL.
    """

    __tablename__ = "article_entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE")
    )
    salience: Mapped[float] = mapped_column()  # 0.0 to 1.0 relevance score
    mention_count: Mapped[int] = mapped_column(default=1)  # Times entity appears
    analyzed_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="article_entities")
    entity: Mapped["Entity"] = relationship(back_populates="article_entities")

    __table_args__ = (
        Index("ix_article_entities_article_id", "article_id"),
        Index("ix_article_entities_entity_id", "entity_id"),
        Index(
            "ix_article_entities_article_entity",
            "article_id",
            "entity_id",
            unique=True,
        ),
        Index("ix_article_entities_salience", "salience"),
    )
