from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from app.schemas.article import ArticleRead


class SourceBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Mediastack source identifier (e.g., 'bbc', 'cnn')",
    )

    @field_validator("name")
    @classmethod
    def validate_source_name(cls, v: str) -> str:
        """Ensure source name follows Mediastack conventions."""
        name = v.strip().lower()
        if not name:
            raise ValueError("Source name cannot be empty")
        # Mediastack sources are typically lowercase, no spaces
        if " " in name:
            raise ValueError("Source name should not contain spaces (use hyphens)")
        return name


class SourceCreate(SourceBase):
    pass


class SourceRead(SourceBase):
    id: int
    created_at: datetime = Field(..., description="When source was added")
    updated_at: datetime = Field(..., description="Last update timestamp")
    articles: Optional[List["ArticleRead"]] = None  # forward ref

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "name": "bbc",
                "created_at": "2025-11-21T12:00:00Z",
                "updated_at": "2025-11-21T12:00:00Z",
            }
        },
    }


from app.schemas.article import ArticleRead  # noqa: F401, E402, F811

SourceRead.model_rebuild()
