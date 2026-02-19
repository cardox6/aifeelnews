from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class ArticleCategory(Base):
    """
    GCP NL content classification categories for articles.

    Stores taxonomy paths like "/News/Business" with confidence scores.
    Simple 1:many from articles (categories are per-article, not deduplicated).
    """

    __tablename__ = "article_categories"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(500), nullable=False)  # Taxonomy path: "/News/Business"
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0

    analyzed_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    article = relationship("Article", back_populates="article_categories")

    __table_args__ = (
        Index("ix_article_categories_article_id", "article_id"),
        Index("ix_article_categories_name", "name"),
        Index("ix_article_categories_confidence", "confidence"),
    )
