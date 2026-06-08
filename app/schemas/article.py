from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.schemas.entity import ArticleCategoryRead, ArticleEntityRead


class ArticleBase(BaseModel):
    """Base model for article data with common validation."""

    title: str = Field(
        ..., min_length=1, max_length=255, description="Article headline"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Article summary or excerpt"
    )
    url: HttpUrl = Field(..., description="Original article URL")
    image_url: Optional[str] = Field(None, description="Article featured image URL")
    published_at: datetime = Field(
        ..., description="When the article was originally published"
    )
    language: Optional[str] = Field(
        None, min_length=2, max_length=2, description="ISO 639-1 language code"
    )
    country: Optional[str] = Field(
        None, min_length=2, max_length=2, description="ISO 3166-1 country code"
    )
    category: Optional[str] = Field(None, max_length=50, description="Article category")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Ensure title is not just whitespace."""
        if not v.strip():
            raise ValueError("Title cannot be empty or just whitespace")
        return v.strip()


class ArticleCreate(ArticleBase):
    """Schema for creating new articles."""

    source_id: int = Field(..., gt=0, description="ID of the news source")

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Write-side validation: reject non-HTTP(S) image URLs on create.

        Lives on ArticleCreate (not ArticleBase) so it does NOT run on the read
        model — a response-model validator that raises on its own stored data
        would turn one bad row into a 500 for the whole list (see
        ArticleRead.coerce_image_url).
        """
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Image URL must be a valid HTTP/HTTPS URL")
        return v


class SourceInArticle(BaseModel):
    """Nested source data in article responses."""

    id: int = Field(..., description="Source identifier")
    name: str = Field(..., description="Source name (e.g., 'BBC', 'CNN')")

    model_config = {
        "from_attributes": True,
    }


class ArticleRead(ArticleBase):
    """Schema for reading article data with sentiment info."""

    id: int = Field(..., description="Unique article identifier")
    source: SourceInArticle = Field(..., description="News source information")

    @field_validator("image_url")
    @classmethod
    def coerce_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Read-side leniency: never RAISE on stored data.

        The write-side ``ArticleBase.validate_image_url`` rejects non-HTTP(S)
        values, but image_url is stored verbatim from upstream feeds and may
        contain e.g. a protocol-relative ``//cdn/x.jpg``. A response-model
        validator that raises on its own stored data turns one bad row into a
        500 for the ENTIRE article list (FastAPI validates the whole
        ``List[ArticleRead]``). Null out a bad value instead of raising so the
        page still serves; the write path keeps the strict check.
        """
        if v and not v.startswith(("http://", "https://")):
            return None
        return v

    # Sentiment analysis results (from latest analysis)
    sentiment_label: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description="Latest sentiment classification"
    )
    sentiment_score: Optional[float] = Field(
        None, ge=-1.0, le=1.0, description="Latest sentiment score (-1 to 1)"
    )
    sentiment_magnitude: Optional[float] = Field(
        None,
        ge=0.0,
        description=(
            "GCP NL sentiment magnitude (emotional intensity, 0+). "
            "NULL for VADER-only articles."
        ),
    )

    # Entity and category data (populated when GCP NL provider is used)
    article_entities: Optional[List[ArticleEntityRead]] = Field(
        default=None,
        description="Named entities extracted from article content",
    )
    article_categories: Optional[List[ArticleCategoryRead]] = Field(
        default=None,
        description="Content categories from GCP NL classification",
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "source_id": 1,
                "title": "Breaking: Major Technology Breakthrough",
                "description": "Scientists achieve quantum computing milestone...",
                "url": "https://example.com/article",
                "image_url": "https://example.com/image.jpg",
                "published_at": "2025-11-21T12:00:00Z",
                "language": "en",
                "country": "us",
                "category": "technology",
                "sentiment_label": "positive",
                "sentiment_score": 0.75,
                "sentiment_magnitude": 2.4,
            }
        },
    }
