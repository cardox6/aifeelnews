from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.user import User


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )

    user: Mapped["User"] = relationship(back_populates="bookmarks")
    article: Mapped["Article"] = relationship(back_populates="bookmarks")

    __table_args__ = (
        Index("ix_bookmarks_user_id", "user_id"),
        Index("ix_bookmarks_article_id", "article_id"),
    )
