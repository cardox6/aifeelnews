"""PostgreSQL-powered analytics endpoints (advanced SQL demonstrations).

These endpoints query the operational database directly using window
functions, CTEs, and GROUPING SETS. They complement the BigQuery
analytics router which handles long-term trend analysis.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.crud.analytics import (
    daily_category_sentiment_pivot,
    entity_momentum,
    sentiment_grouping_sets,
    sentiment_rolling_average,
    source_sentiment_ranked,
)
from app.database import get_db

router = APIRouter(tags=["DB Analytics"])


@router.get("/sentiment/rolling", response_model=List[Dict[str, Any]])
def get_sentiment_rolling(
    days: int = Query(30, ge=7, le=365),
    window: int = Query(7, ge=3, le=30, description="Rolling window size in days"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """7-day rolling average sentiment trend (window function)."""
    return sentiment_rolling_average(db, days=days, window=window)


@router.get("/sources/ranked", response_model=List[Dict[str, Any]])
def get_sources_ranked(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Sources ranked by average sentiment (CTE + RANK window function)."""
    return source_sentiment_ranked(db, days=days)


@router.get("/sentiment/breakdown", response_model=List[Dict[str, Any]])
def get_sentiment_breakdown(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Multi-dimensional sentiment breakdown (GROUPING SETS)."""
    return sentiment_grouping_sets(db, days=days)


@router.get("/entities/momentum", response_model=List[Dict[str, Any]])
def get_entity_momentum(
    days: int = Query(14, ge=4, le=60),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Entity mention momentum: this period vs previous period."""
    return entity_momentum(db, days=days)


@router.get("/categories/daily", response_model=List[Dict[str, Any]])
def get_categories_daily(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Daily sentiment per category with cumulative totals (window function)."""
    return daily_category_sentiment_pivot(db, days=days)
