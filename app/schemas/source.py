from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    """Lean source representation used by ``GET /sources/``.

    The relationship to articles is intentionally NOT included here. Returning
    every article on every source produces an N+1 explosion via Pydantic's
    ``from_attributes`` serialization (each Source's ``articles`` lazy-loads,
    and every Article then loads its own eager-load chain), which timed out
    the route at the 300s Cloud Run boundary in production. If a future
    endpoint needs the nested-articles shape, define a separate
    ``SourceWithArticlesRead`` and use ``selectinload`` to keep it bounded.
    """

    id: int
    created_at: datetime = Field(..., description="When source was added")
    updated_at: datetime = Field(..., description="Last update timestamp")

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
