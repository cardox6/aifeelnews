from typing import List, Dict, Any
from datetime import datetime

def normalize_article(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a single raw article dict from Mediastack."""
    return {
        "source_name": raw.get("source"),
        "title": raw.get("title"),
        "description": raw.get("description"),
        "url": raw.get("url"),
        "image_url": raw.get("image"),
        "published_at": parse_datetime(raw.get("published_at")),
        "language": raw.get("language"),
        "country": raw.get("country"),
        "category": raw.get("category"),
    }

def parse_datetime(date_str: str) -> datetime:
    """Parse ISO datetime string into Python datetime object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        return None

def normalize_articles(raw_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a list of raw articles."""
    return [normalize_article(article) for article in raw_articles]
