from pydantic import BaseModel
from typing import List
from .bookmark import BookmarkOut

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int

class UserOut(BaseModel):
    id: int
    email: str
    bookmarks: List[BookmarkOut] = []

    class Config:
        orm_mode = True
