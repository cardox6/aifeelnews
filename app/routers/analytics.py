"""BigQuery-powered analytics endpoints for dashboard consumption."""

from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Query

from app.config import config
from app.schemas.analytics import (
    CategoryBreakdown,
    EntitySentiment,
    NlpCategoryBreakdown,
    PipelineRun,
    SentimentTrendPoint,
    SourceComparison,
    TopEntity,
)
from app.services.bigquery import (
    get_category_breakdown,
    get_entity_sentiment,
    get_nlp_categories,
    get_pipeline_stats,
    get_sentiment_trends,
    get_source_comparison,
    get_top_entities,
)

router = APIRouter(tags=["Analytics"])


def _disabled_response() -> Dict[str, str]:
    return {"message": "BigQuery analytics is not enabled"}


@router.get(
    "/trends",
    response_model=Union[List[SentimentTrendPoint], Dict[str, str]],
)
def sentiment_trends(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    source: Optional[str] = Query(None, description="Filter by source name"),
) -> Union[List[SentimentTrendPoint], Dict[str, str]]:
    """Sentiment trends over time, optionally filtered by news source."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [SentimentTrendPoint(**row) for row in get_sentiment_trends(days, source)]


@router.get(
    "/sources",
    response_model=Union[List[SourceComparison], Dict[str, str]],
)
def source_comparison(
    days: int = Query(30, ge=1, le=365),
) -> Union[List[SourceComparison], Dict[str, str]]:
    """Compare sentiment distribution across news sources."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [SourceComparison(**row) for row in get_source_comparison(days)]


@router.get(
    "/categories",
    response_model=Union[List[CategoryBreakdown], Dict[str, str]],
)
def category_breakdown(
    days: int = Query(30, ge=1, le=365),
) -> Union[List[CategoryBreakdown], Dict[str, str]]:
    """Sentiment breakdown by article category."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [CategoryBreakdown(**row) for row in get_category_breakdown(days)]


@router.get(
    "/pipeline",
    response_model=Union[List[PipelineRun], Dict[str, str]],
)
def pipeline_health(
    days: int = Query(7, ge=1, le=90),
) -> Union[List[PipelineRun], Dict[str, str]]:
    """Ingestion pipeline run history and health metrics."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [PipelineRun(**row) for row in get_pipeline_stats(days)]


@router.get(
    "/entities/top",
    response_model=Union[List[TopEntity], Dict[str, str]],
)
def top_entities(
    days: int = Query(30, ge=1, le=365),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(20, ge=1, le=100),
) -> Union[List[TopEntity], Dict[str, str]]:
    """Top entities by article mention count, with average sentiment."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [TopEntity(**row) for row in get_top_entities(days, entity_type, limit)]


@router.get(
    "/entities/sentiment",
    response_model=Union[List[EntitySentiment], Dict[str, str]],
)
def entity_sentiment(
    days: int = Query(30, ge=1, le=365),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(20, ge=1, le=100),
) -> Union[List[EntitySentiment], Dict[str, str]]:
    """Per-entity sentiment statistics (entities appearing in 2+ articles)."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [
        EntitySentiment(**row) for row in get_entity_sentiment(days, entity_type, limit)
    ]


@router.get(
    "/categories/nlp",
    response_model=Union[List[NlpCategoryBreakdown], Dict[str, str]],
)
def nlp_categories(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
) -> Union[List[NlpCategoryBreakdown], Dict[str, str]]:
    """GCP NL content categories with sentiment aggregation."""
    if not config.bigquery.enable_bigquery:
        return _disabled_response()
    return [NlpCategoryBreakdown(**row) for row in get_nlp_categories(days, limit)]
