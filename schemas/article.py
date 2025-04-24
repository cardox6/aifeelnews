from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ArticleBase(BaseModel):
    source_id: int  # Replace 'source' with 'source_id'
    title: str
    description: Optional[str]
    url: str
    image_url: Optional[str]
    published_at: Optional[datetime]
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    id: int

    class Config:
        orm_mode = True
