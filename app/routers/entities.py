"""Entity analysis API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.constants.entity_filters import publisher_denylist_lower
from app.database import get_db
from app.models.article_entity import ArticleEntity
from app.models.entity import Entity
from app.schemas.entity import EntityRead, EntityWithArticleCount

router = APIRouter(tags=["Entities"])


@router.get("/", response_model=List[EntityWithArticleCount])
def list_entities(
    db: Session = Depends(get_db),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    min_articles: int = Query(1, ge=1, description="Minimum article count"),
) -> list:
    """
    List entities ordered by frequency (number of articles mentioning them).

    Applies the same quality gate as the analytics entity charts
    (``app/constants/entity_filters.py``): Knowledge-Graph-resolved only
    (``wikipedia_url IS NOT NULL``) and excluding the publisher denylist.
    """
    query = (
        db.query(
            Entity,
            func.count(ArticleEntity.id).label("article_count"),
        )
        .join(ArticleEntity, Entity.id == ArticleEntity.entity_id)
        .filter(Entity.wikipedia_url.isnot(None))
        .filter(func.lower(Entity.name).notin_(publisher_denylist_lower()))
        .group_by(Entity.id)
        .having(func.count(ArticleEntity.id) >= min_articles)
        .order_by(func.count(ArticleEntity.id).desc())
    )

    if entity_type:
        query = query.filter(Entity.type == entity_type.upper())

    results = query.limit(limit).all()

    return [
        EntityWithArticleCount(
            id=entity.id,
            name=entity.name,
            type=entity.type,
            wikipedia_url=entity.wikipedia_url,
            mid=entity.mid,
            article_count=count,
        )
        for entity, count in results
    ]


@router.get("/types", response_model=List[str])
def list_entity_types(db: Session = Depends(get_db)) -> list:
    """List all distinct entity types in the database."""
    types = db.query(Entity.type).distinct().order_by(Entity.type).all()
    return [t[0] for t in types]


@router.get("/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: int, db: Session = Depends(get_db)) -> EntityRead:
    """Get a single entity by ID."""
    entity = db.query(Entity).filter_by(id=entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity  # type: ignore[return-value,no-any-return]
