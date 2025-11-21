from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


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

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Basic image URL validation."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Image URL must be a valid HTTP/HTTPS URL")
        return v


class ArticleCreate(ArticleBase):
    """Schema for creating new articles."""

    source_id: int = Field(..., gt=0, description="ID of the news source")


class ArticleRead(ArticleBase):
    """Schema for reading article data with sentiment info."""

    id: int = Field(..., description="Unique article identifier")
    source_id: int = Field(..., description="ID of the news source")

    # Sentiment analysis results (from latest analysis)
    sentiment_label: Optional[Literal["positive", "negative", "neutral"]] = Field(
        None, description="Latest sentiment classification"
    )
    sentiment_score: Optional[float] = Field(
        None, ge=-1.0, le=1.0, description="Latest sentiment score (-1 to 1)"
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
            }
        },
    }
