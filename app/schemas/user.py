from typing import List, Optional

from pydantic import BaseModel, EmailStr


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
