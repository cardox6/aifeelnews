from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, func
from sqlalchemy.orm import relationship

from app.database import Base


class ArticleEntity(Base):
    """
    Association table for the Article <-> Entity M2M relationship.

    Each row represents one entity mention within one article,
    storing the article-specific salience score from GCP NL.
    """

    __tablename__ = "article_entities"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    entity_id = Column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    salience = Column(Float, nullable=False)  # 0.0 to 1.0 relevance score
    analyzed_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    article = relationship("Article", back_populates="article_entities")
    entity = relationship("Entity", back_populates="article_entities")

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
