from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Bookmark(Base):
    __tablename__ = "bookmarks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    article_id = Column(Integer, ForeignKey("articles.id"))

    user = relationship("User", back_populates="bookmarks")
    article = relationship("Article", back_populates="bookmarks")
