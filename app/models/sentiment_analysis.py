from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class SentimentAnalysis(Base):
    __tablename__ = "sentiment_analyses"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    provider = Column(
        String(50), nullable=False
    )  # e.g., 'VADER', 'GCP_NL', 'AZURE_TEXT'
    model_name = Column(
        String(100), nullable=True
    )  # e.g., 'vader_lexicon', 'gcp_nl_v1'
    score = Column(Float, nullable=False)  # Sentiment score (-1.0 to 1.0)
    magnitude = Column(Float, nullable=True)  # GCP NL magnitude (0.0 to infinity)
    label = Column(String(20), nullable=False)  # 'positive', 'negative', 'neutral'
    language = Column(String(10), nullable=True)  # Detected language code
    analyzed_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    article = relationship("Article", back_populates="sentiment_analyses")

    __table_args__ = (
        Index("ix_sentiment_analyses_article_id", "article_id"),
        Index("ix_sentiment_analyses_provider", "provider"),
        Index("ix_sentiment_analyses_analyzed_at", "analyzed_at"),
        Index("ix_sentiment_analyses_label", "label"),
        # Composite index for provider + article lookups
        Index("ix_sentiment_analyses_provider_article", "provider", "article_id"),
    )
