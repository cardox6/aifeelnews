from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article_category import ArticleCategory
    from app.models.article_content import ArticleContent
    from app.models.article_entity import ArticleEntity
    from app.models.bookmark import Bookmark
    from app.models.crawl_job import CrawlJob
    from app.models.sentiment_analysis import SentimentAnalysis
    from app.models.source import Source


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), default=None)
    published_at: Mapped[datetime] = mapped_column(index=True)
    language: Mapped[Optional[str]] = mapped_column(String(2), default=None)
    country: Mapped[Optional[str]] = mapped_column(String(2), default=None)
    category: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    sentiment_score: Mapped[Optional[float]] = mapped_column(default=None)

    source: Mapped["Source"] = relationship(back_populates="articles")
    bookmarks: Mapped[List["Bookmark"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )
    crawl_jobs: Mapped[List["CrawlJob"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )
    content: Mapped[Optional["ArticleContent"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )
    sentiment_analyses: Mapped[List["SentimentAnalysis"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )
    article_entities: Mapped[List["ArticleEntity"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )
    article_categories: Mapped[List["ArticleCategory"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select",
    )
