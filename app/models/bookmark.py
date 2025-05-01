from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="bookmarks")
    article = relationship("Article", back_populates="bookmarks")
