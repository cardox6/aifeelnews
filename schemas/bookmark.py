from pydantic import BaseModel
from typing import Optional

class BookmarkBase(BaseModel):
    user_id: int
    article_id: int

class BookmarkCreate(BookmarkBase):
    pass

class Bookmark(BookmarkBase):
    id: int

class BookmarkOut(BaseModel):
    id: int
    user_id: int
    article_id: int

    class Config:
        orm_mode = True
