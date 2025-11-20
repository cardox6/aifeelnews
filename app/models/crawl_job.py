import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class CrawlStatus(enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    FORBIDDEN_BY_ROBOTS = "FORBIDDEN_BY_ROBOTS"
    RATE_LIMITED = "RATE_LIMITED"


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(Enum(CrawlStatus), nullable=False, default=CrawlStatus.PENDING)
    robots_allowed = Column(Boolean, nullable=True)
    http_status = Column(Integer, nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    bytes_downloaded = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    article = relationship("Article", back_populates="crawl_jobs")

    __table_args__ = (
        Index("ix_crawl_jobs_status", "status"),
        Index("ix_crawl_jobs_article_id", "article_id"),
        Index("ix_crawl_jobs_created_at", "created_at"),
    )
