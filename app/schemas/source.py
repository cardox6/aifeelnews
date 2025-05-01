from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.schemas.article import ArticleRead


class SourceBase(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=255, description="Unique name of the news source"
    )


class SourceCreate(SourceBase):
    pass


class SourceRead(SourceBase):
    id: int
    articles: Optional[List["ArticleRead"]] = None  # forward ref

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


from app.schemas.article import ArticleRead  # noqa: F401, E402, F811

SourceRead.model_rebuild()
