from pydantic import BaseModel, EmailStr
from typing import List, Optional


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int

    bookmarks: Optional[List[int]] = []

    model_config = {
        "from_attributes": True,
    }
