"""Database cleanup utilities for maintaining data hygiene."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.article_content import ArticleContent


def cleanup_expired_content(db: Session) -> Dict[str, Any]:
    """
    Remove expired article content based on TTL configuration.

    Args:
        db: Database session

    Returns:
        dict: Cleanup results with counts and statistics
    """
    now = datetime.now(timezone.utc)

    # Count expired records before deletion
    expired_count = (
        db.query(ArticleContent).filter(ArticleContent.expires_at <= now).count()
    )

    # Delete expired content
    deleted = db.query(ArticleContent).filter(ArticleContent.expires_at <= now).delete()

    db.commit()

    # Get remaining content statistics
    total_remaining = db.query(ArticleContent).count()

    # Get oldest and newest content dates
    oldest_content = db.query(func.min(ArticleContent.extracted_at)).scalar()
    newest_content = db.query(func.max(ArticleContent.extracted_at)).scalar()

    return {
        "expired_content_deleted": deleted,
        "expired_content_found": expired_count,
        "total_content_remaining": total_remaining,
        "oldest_content_date": oldest_content.isoformat() if oldest_content else None,
        "newest_content_date": newest_content.isoformat() if newest_content else None,
        "cleanup_timestamp": now.isoformat(),
    }


def cleanup_old_crawl_jobs(db: Session, days_old: int = 7) -> Dict[str, Any]:
    """
    Clean up old crawl job records to prevent table bloat.

    Args:
        db: Database session
        days_old: Remove records older than this many days

    Returns:
        dict: Cleanup results
    """
    from datetime import timedelta

    from app.models.crawl_job import CrawlJob

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

    # Count old records
    old_count = (
        db.query(CrawlJob)
        .filter(CrawlJob.created_at < cutoff_date)
        .filter(CrawlJob.status.in_(["COMPLETED", "FAILED", "FORBIDDEN_BY_ROBOTS"]))
        .count()
    )

    # Delete old completed/failed crawl jobs
    deleted = (
        db.query(CrawlJob)
        .filter(CrawlJob.created_at < cutoff_date)
        .filter(CrawlJob.status.in_(["COMPLETED", "FAILED", "FORBIDDEN_BY_ROBOTS"]))
        .delete()
    )

    db.commit()

    return {
        "old_crawl_jobs_deleted": deleted,
        "old_crawl_jobs_found": old_count,
        "cutoff_date": cutoff_date.isoformat(),
    }


def get_database_stats(db: Session) -> Dict[str, Any]:
    """
    Get general database statistics for monitoring.

    Args:
        db: Database session

    Returns:
        dict: Database statistics
    """
    from app.models.article import Article
    from app.models.crawl_job import CrawlJob
    from app.models.sentiment_analysis import SentimentAnalysis
    from app.models.source import Source

    # Get table counts
    stats: Dict[str, Any] = {
        "sources_count": db.query(Source).count(),
        "articles_count": db.query(Article).count(),
        "article_contents_count": db.query(ArticleContent).count(),
        "crawl_jobs_count": db.query(CrawlJob).count(),
        "sentiment_analyses_count": db.query(SentimentAnalysis).count(),
    }

    # Get crawl job status breakdown
    crawl_status_stats = (
        db.query(CrawlJob.status, func.count(CrawlJob.id))
        .group_by(CrawlJob.status)
        .all()
    )

    stats["crawl_job_status"] = {
        str(status): int(count) for status, count in crawl_status_stats
    }

    # Get recent activity
    recent_articles = (
        db.query(func.count(Article.id))
        .filter(
            Article.published_at >= datetime.now(timezone.utc) - timedelta(hours=24)
        )
        .scalar()
    )

    stats["articles_last_24h"] = recent_articles

    return stats


def full_database_cleanup(db: Session) -> Dict[str, Any]:
    """
    Perform comprehensive database cleanup.

    Args:
        db: Database session

    Returns:
        dict: Combined cleanup results
    """
    results: Dict[str, Any] = {
        "cleanup_started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Cleanup expired content
    try:
        content_cleanup = cleanup_expired_content(db)
        results["content_cleanup"] = content_cleanup
    except Exception as e:
        results["content_cleanup_error"] = str(e)

    # Cleanup old crawl jobs
    try:
        crawl_cleanup = cleanup_old_crawl_jobs(db)
        results["crawl_job_cleanup"] = crawl_cleanup
    except Exception as e:
        results["crawl_job_cleanup_error"] = str(e)

    # Get updated stats
    try:
        stats = get_database_stats(db)
        results["database_stats"] = stats
    except Exception as e:
        results["stats_error"] = str(e)

    results["cleanup_completed_at"] = datetime.now(timezone.utc).isoformat()

    return results
