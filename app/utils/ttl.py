"""Utility functions for TTL (Time To Live) management."""

from datetime import datetime, timedelta, timezone

from app.config import settings


def calculate_content_expiry() -> datetime:
    """
    Calculate the expiry timestamp for article content based on configured TTL.

    Returns:
        datetime: UTC timestamp when content should expire
    """
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(hours=settings.ARTICLE_CONTENT_TTL_HOURS)
    return expiry


def get_ttl_info() -> dict:
    """
    Get TTL configuration information for monitoring.

    Returns:
        dict: TTL configuration details
    """
    return {
        "ttl_hours": settings.ARTICLE_CONTENT_TTL_HOURS,
        "ttl_description": f"Article content expires after {settings.ARTICLE_CONTENT_TTL_HOURS} hours",
        "current_utc": datetime.now(timezone.utc).isoformat(),
        "next_expiry_would_be": calculate_content_expiry().isoformat(),
    }
