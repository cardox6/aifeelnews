from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    url = Column(String, unique=True, nullable=False)
    image_url = Column(String)
    published_at = Column(DateTime, index=True)
    sentiment_label = Column(String)
    sentiment_score = Column(Float)

    source_obj = relationship("Source", back_populates="articles")
