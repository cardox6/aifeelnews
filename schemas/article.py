from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ArticleBase(BaseModel):
    title: str
    description: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    published_at: datetime
    language: Optional[str] = None 
    country: Optional[str] = None
    category: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None

class ArticleCreate(ArticleBase):
    source_id: int

class Article(ArticleBase):
    id: int
    source_id: int

    class Config:
        orm_mode = True
