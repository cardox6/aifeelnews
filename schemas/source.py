from pydantic import BaseModel
from typing import Optional

class SourceBase(BaseModel):
    name: str

class SourceCreate(SourceBase):
    pass

class SourceOut(SourceBase):
    id: int

    class Config:
        orm_mode = True
