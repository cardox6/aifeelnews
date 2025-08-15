from sqlalchemy import (Column, DateTime, Float, ForeignKey, Index, Integer,
                        String)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.source import Source  # noqa: F401


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    url = Column(String(1000), unique=True, nullable=False)
    image_url = Column(String(1000), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    language = Column(String(2), nullable=True)
    country = Column(String(2), nullable=True)
    category = Column(String(50), nullable=True)
    sentiment_label = Column(String(20), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    author = Column(String(25), nullable=True)

    source = relationship("Source", back_populates="articles")
    bookmarks = relationship(
        "Bookmark",
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (Index("ix_articles_published_at", "published_at"),)
