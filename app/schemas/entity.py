from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EntityRead(BaseModel):
    """Schema for reading a canonical entity."""

    id: int
    name: str = Field(..., description="Entity name (e.g., 'Google')")
    type: str = Field(..., description="Entity type (e.g., 'ORGANIZATION')")
    wikipedia_url: Optional[str] = Field(None, description="Wikipedia URL if available")
    mid: Optional[str] = Field(None, description="Google Knowledge Graph MID")

    model_config = {"from_attributes": True}


class ArticleEntityRead(BaseModel):
    """Schema for an entity associated with an article."""

    id: int
    entity: EntityRead = Field(..., description="The canonical entity")
    salience: float = Field(..., ge=0.0, le=1.0, description="Relevance to article")
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class ArticleCategoryRead(BaseModel):
    """Schema for a GCP NL category associated with an article."""

    id: int
    name: str = Field(..., description="Taxonomy path (e.g., '/News/Business')")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence"
    )
    analyzed_at: datetime

    model_config = {"from_attributes": True}


class EntityWithArticleCount(BaseModel):
    """Entity with count of associated articles, for the entities listing endpoint."""

    id: int
    name: str
    type: str
    wikipedia_url: Optional[str] = None
    mid: Optional[str] = None
    article_count: int = Field(
        ..., description="Number of articles mentioning this entity"
    )

    model_config = {"from_attributes": True}
