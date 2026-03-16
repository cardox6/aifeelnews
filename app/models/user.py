from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.bookmark import Bookmark


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, default=None)
    firebase_uid: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, default=None
    )

    bookmarks: Mapped[List["Bookmark"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
