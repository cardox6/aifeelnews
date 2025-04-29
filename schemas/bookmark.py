from pydantic import BaseModel

class BookmarkBase(BaseModel):
    article_id: int

class BookmarkCreate(BookmarkBase):
    pass

class Bookmark(BookmarkBase):
    id: int


class BookmarkRead(BaseModel):
    id: int
    article_id: int
    user_id: int

    class Config:
        orm_mode = True
