from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article


class ArticleCategory(Base):
    """
    GCP NL content classification categories for articles.

    Stores taxonomy paths like "/News/Business" with confidence scores.
    Simple 1:many from articles (categories are per-article, not deduplicated).
    """

    __tablename__ = "article_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(500))  # Taxonomy path: "/News/Business"
    confidence: Mapped[float] = mapped_column()  # 0.0 to 1.0
    analyzed_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="article_categories")

    __table_args__ = (
        Index("ix_article_categories_article_id", "article_id"),
        Index("ix_article_categories_name", "name"),
        Index("ix_article_categories_confidence", "confidence"),
    )
