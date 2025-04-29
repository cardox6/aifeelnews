from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, unique=True, nullable=False)
    image_url = Column(String, nullable=True)
    published_at = Column(DateTime, index=True)
    language = Column(String, nullable=True)
    country = Column(String, nullable=True)
    category = Column(String, nullable=True)

    sentiment_label = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    source_obj = relationship("Source", back_populates="articles")

    bookmarks = relationship("Bookmark", back_populates="article", cascade="all, delete")
