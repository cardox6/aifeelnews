import requests
from datetime import date
from config import settings

def fetch_articles_from_sources(source: str) -> list[dict]:
    """Fetch today´s articles for a single source from Mediastack API."""
    params = {
        "access_key": settings.MEDIASTACK_API_KEY,
        "sources": source,
        "languages": settings.LANGUAGES,
        "categories": settings.CATEGORIES,
        "sort": "published_desc",
        "limit": settings.PAGESIZE,
        "date": date.today().isoformat(),
    }
    resp = requests.get(settings.MEDIASTACK_BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("data", [])