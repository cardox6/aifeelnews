from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.database import get_db
from app.models.article import Article as ArticleModel
from app.models.article_entity import ArticleEntity
from app.schemas.article import ArticleRead

router = APIRouter(tags=["Articles"])


def _query_articles(
    db: Session,
    skip: int,
    limit: int,
    sentiment_label: str | None,
    category: str | None,
    source_id: int | None,
    search: str | None,
) -> list[ArticleModel]:
    """Build the article-list query with optional filters and pagination.

    The filter columns (sentiment_label, category, source_id) are indexed in
    migration ``f2a3b4c5d6e7`` so filter+order is index-supported. Substring
    search on title is unindexed; production-grade search would use pg_trgm
    GIN.
    """
    query = db.query(ArticleModel).options(
        joinedload(ArticleModel.source),
        joinedload(ArticleModel.sentiment_analyses),
        subqueryload(ArticleModel.article_entities).joinedload(ArticleEntity.entity),
        subqueryload(ArticleModel.article_categories),
    )
    if sentiment_label is not None:
        query = query.filter(ArticleModel.sentiment_label == sentiment_label)
    if category is not None:
        query = query.filter(ArticleModel.category == category)
    if source_id is not None:
        query = query.filter(ArticleModel.source_id == source_id)
    if search is not None:
        query = query.filter(ArticleModel.title.ilike(f"%{search}%"))
    return list(
        query.order_by(
            ArticleModel.published_at.desc(),
            ArticleModel.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/", response_model=List[ArticleRead])
def get_articles(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Pagination offset (zero-based)"),
    limit: int = Query(20, ge=1, le=100, description="Page size; capped at 100"),
    sentiment_label: str | None = Query(
        None,
        pattern="^(positive|negative|neutral)$",
        description="Filter by sentiment label",
    ),
    category: str | None = Query(None, max_length=50),
    source_id: int | None = Query(None, ge=1),
    search: str | None = Query(
        None,
        min_length=2,
        max_length=200,
        description="Case-insensitive substring match against article title",
    ),
) -> List[ArticleRead]:
    return _query_articles(  # type: ignore[return-value]
        db, skip, limit, sentiment_label, category, source_id, search
    )


@router.get("/latest", response_model=List[ArticleRead])
def get_latest_articles(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(40, ge=1, le=100),
    sentiment_label: str | None = Query(None, pattern="^(positive|negative|neutral)$"),
    category: str | None = Query(None, max_length=50),
    source_id: int | None = Query(None, ge=1),
    search: str | None = Query(None, min_length=2, max_length=200),
) -> List[ArticleRead]:
    return _query_articles(  # type: ignore[return-value]
        db, skip, limit, sentiment_label, category, source_id, search
    )


@router.get("/{article_id}", response_model=ArticleRead)
def get_article(article_id: int, db: Session = Depends(get_db)) -> ArticleRead:
    article = (
        db.query(ArticleModel)
        .options(
            joinedload(ArticleModel.source),
            subqueryload(ArticleModel.article_entities).joinedload(
                ArticleEntity.entity
            ),
            subqueryload(ArticleModel.article_categories),
        )
        .filter_by(id=article_id)
        .first()
    )
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article  # type: ignore[return-value,no-any-return]
