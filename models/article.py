from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import relationship
from database import Base

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    url = Column(String, unique=True, nullable=False)
    image_url = Column(String)
    published_at = Column(DateTime, index=True)

    sentiment_label = Column(String)
    sentiment_score = Column(Float)

    bookmarks = relationship("Bookmark", back_populates="article")
