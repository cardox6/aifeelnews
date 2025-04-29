from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime
from typing import Optional

class ArticleBase(BaseModel):
    source_id: int

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        regex=r"^[A-Za-z0-9].*"
    )

    description: Optional[str] = Field(None, max_length=1000)
    url:         HttpUrl
    image_url:   Optional[str] = None
    published_at: datetime
    language: Optional[str] = Field(None, max_length=2)
    country: Optional[str] = Field(None, max_length=2)
    category: Optional[str] = Field(None, max_length=50)

    sentiment_label: Optional[str] = Field(None, max_length=20)
    sentiment_score: Optional[float] = None

class ArticleCreate(ArticleBase):
    pass

class ArticleRead(ArticleBase):
    id: int

    class Config:
        orm_mode = True
