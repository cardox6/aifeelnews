"""Response models for BigQuery analytics endpoints."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class SentimentTrendPoint(BaseModel):
    """A single data point in a sentiment trend time series."""

    date: date
    sentiment_label: str
    article_count: int
    avg_sentiment_score: float
    avg_magnitude: Optional[float] = None


class SourceComparison(BaseModel):
    """Sentiment distribution for a single news source."""

    source_name: str
    sentiment_label: str
    article_count: int
    avg_sentiment_score: float
    percentage: float = Field(description="Percentage of this label within the source")


class CategoryBreakdown(BaseModel):
    """Sentiment aggregation for an article category."""

    category: str
    article_count: int
    avg_sentiment_score: float
    avg_magnitude: Optional[float] = None


class PipelineRun(BaseModel):
    """A single ingestion pipeline run record."""

    run_id: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    articles_fetched: int
    articles_ingested: int
    crawl_successful: Optional[int] = None
    crawl_failed: Optional[int] = None
    include_crawling: bool


class TopEntity(BaseModel):
    """Top entity by article mention count."""

    entity_name: str
    entity_type: str
    article_count: int
    avg_salience: Optional[float] = None
    avg_sentiment_score: Optional[float] = None


class EntitySentiment(BaseModel):
    """Per-entity sentiment statistics."""

    entity_name: str
    entity_type: str
    article_count: int
    avg_sentiment_score: Optional[float] = None
    avg_salience: Optional[float] = None


class NlpCategoryBreakdown(BaseModel):
    """GCP NL content category with sentiment aggregation."""

    category_name: str
    article_count: int
    avg_confidence: Optional[float] = None
    avg_sentiment_score: Optional[float] = None
