from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.article import Article


class ArticleContent(Base):
    __tablename__ = "article_contents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), unique=True
    )
    content_text: Mapped[str] = mapped_column(Text)  # TRUNCATED to max 1024 chars
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 hash
    content_length: Mapped[int] = (
        mapped_column()
    )  # Original full length before truncation
    extracted_at: Mapped[datetime] = mapped_column(default=func.now())
    expires_at: Mapped[datetime] = mapped_column()  # TTL cleanup

    # Relationships
    article: Mapped["Article"] = relationship(back_populates="content")

    __table_args__ = (
        Index("ix_article_contents_expires_at", "expires_at"),
        Index("ix_article_contents_extracted_at", "extracted_at"),
        Index("ix_article_contents_content_hash", "content_hash"),
    )
