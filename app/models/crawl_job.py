import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article


class CrawlStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    FORBIDDEN_BY_ROBOTS = "FORBIDDEN_BY_ROBOTS"
    RATE_LIMITED = "RATE_LIMITED"


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )
    status: Mapped[CrawlStatus] = mapped_column(
        Enum(CrawlStatus), default=CrawlStatus.PENDING
    )
    robots_allowed: Mapped[Optional[bool]] = mapped_column(default=None)
    http_status: Mapped[Optional[int]] = mapped_column(default=None)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(default=None)
    bytes_downloaded: Mapped[Optional[int]] = mapped_column(default=None)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="crawl_jobs")

    __table_args__ = (
        Index("ix_crawl_jobs_status", "status"),
        Index("ix_crawl_jobs_article_id", "article_id"),
        Index("ix_crawl_jobs_created_at", "created_at"),
    )
