from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article


class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(50))  # e.g., 'VADER', 'GCP_NL'
    model_name: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    score: Mapped[float] = mapped_column()  # Sentiment score (-1.0 to 1.0)
    magnitude: Mapped[Optional[float]] = mapped_column(default=None)  # GCP NL magnitude
    label: Mapped[str] = mapped_column(String(20))  # 'positive', 'negative', 'neutral'
    language: Mapped[Optional[str]] = mapped_column(String(10), default=None)
    analyzed_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="sentiment_analyses")

    __table_args__ = (
        Index("ix_sentiment_analyses_article_id", "article_id"),
        Index("ix_sentiment_analyses_provider", "provider"),
        Index("ix_sentiment_analyses_analyzed_at", "analyzed_at"),
        Index("ix_sentiment_analyses_label", "label"),
        Index("ix_sentiment_analyses_provider_article", "provider", "article_id"),
    )
