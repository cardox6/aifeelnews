from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class ArticleContent(Base):
    __tablename__ = "article_contents"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content_text = Column(Text, nullable=False)  # TRUNCATED to max 1024 chars
    content_hash = Column(String(64), nullable=False)  # SHA-256 hash
    content_length = Column(
        Integer, nullable=False
    )  # Original full length before truncation
    extracted_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)  # TTL cleanup

    # Relationships
    article = relationship("Article", back_populates="content")

    __table_args__ = (
        Index("ix_article_contents_expires_at", "expires_at"),
        Index("ix_article_contents_extracted_at", "extracted_at"),
        Index("ix_article_contents_content_hash", "content_hash"),
    )
