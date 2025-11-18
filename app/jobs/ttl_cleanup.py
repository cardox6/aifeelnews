"""
TTL cleanup job for article contents.

This job removes expired article content snippets to ensure data compliance.
Should be run periodically (e.g., hourly via cron or task scheduler).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.article_content import ArticleContent
from app.utils.ttl import get_ttl_info

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_expired_content(db: Session | None = None) -> dict:
    """
    Remove expired article content based on expires_at TTL.

    Returns:
        dict: Cleanup statistics including count of deleted records
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        now = datetime.now(timezone.utc)

        # Find expired content
        expired_query = db.query(ArticleContent).filter(
            ArticleContent.expires_at <= now
        )

        expired_count = expired_query.count()

        if expired_count > 0:
            logger.info(f"Found {expired_count} expired article contents to cleanup")

            # Delete expired content
            deleted_count = expired_query.delete(synchronize_session=False)
            db.commit()

            logger.info(
                f"Successfully cleaned up {deleted_count} expired article contents"
            )

            return {
                "status": "success",
                "deleted_count": deleted_count,
                "cleanup_time": now.isoformat(),
            }
        else:
            logger.info("No expired article contents found")
            return {
                "status": "success",
                "deleted_count": 0,
                "cleanup_time": now.isoformat(),
            }

    except Exception as e:
        db.rollback()
        logger.error(f"Error during TTL cleanup: {str(e)}")
        error_time = datetime.now(timezone.utc)
        return {
            "status": "error",
            "error": str(e),
            "deleted_count": 0,
            "cleanup_time": error_time.isoformat(),
        }
    finally:
        if should_close:
            db.close()


def get_content_statistics(db: Session | None = None) -> dict:
    """
    Get statistics about article content storage for monitoring.

    Returns:
        dict: Statistics including total, expired, and space usage
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        now = datetime.now(timezone.utc)

        # Total content records
        total_count = db.query(ArticleContent).count()

        # Expired but not yet cleaned up
        expired_count = (
            db.query(ArticleContent).filter(ArticleContent.expires_at <= now).count()
        )

        # Active content (not expired)
        active_count = total_count - expired_count

        # Average content length
        avg_length = db.query(func.avg(ArticleContent.content_length)).scalar() or 0

        return {
            "total_records": total_count,
            "active_records": active_count,
            "expired_records": expired_count,
            "average_content_length": round(avg_length, 2),
            "check_time": now.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting content statistics: {str(e)}")
        error_time = datetime.now(timezone.utc)
        return {"error": str(e), "check_time": error_time.isoformat()}
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    """Run TTL cleanup as a standalone script."""
    logger.info("Starting TTL cleanup job")
    
    # Show TTL configuration
    ttl_info = get_ttl_info()
    print(f"TTL Configuration: {ttl_info}")
    
    # Run cleanup
    result = cleanup_expired_content()
    print(f"Cleanup result: {result}")

    # Show statistics
    stats = get_content_statistics()
    print(f"Content statistics: {stats}")
