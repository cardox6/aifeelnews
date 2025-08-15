import logging
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import ssl
from urllib.parse import urlparse

from app.config import settings
from app.jobs.sources_list import SOURCES

logger = logging.getLogger(__name__)

class SecurityError(Exception):
    """Custom exception for SSL verification errors."""
    pass

def validate_url_security(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SecurityError(f"Insecure protocol '{parsed.scheme}' not allowed. Use HTTPS only.")
    
    allowed_domains = settings.ALLOWED_DOMAINS
    if not any(parsed.netloc.endswith(domain) for domain in allowed_domains):
        raise SecurityError(f"Domain '{parsed.netloc}' is not in the allowed list: {allowed_domains}")
    return True

def fetch_articles_from_source(source: str) -> list[dict]:
    base_params = {
        "access_key": settings.MEDIASTACK_API_KEY,
        "sources": source,
        "languages": settings.MEDIASTACK_LANGUAGES,
        "sort": settings.MEDIASTACK_SORT,
        "categories": settings.MEDIASTACK_FETCH_CATEGORIES,
        "limit": settings.MEDIASTACK_FETCH_LIMIT,
        "date": date.today().isoformat(),
    }

    resp = requests.get(
        settings.MEDIASTACK_BASE_URL,
        params=base_params,
        timeout=settings.MEDIASTACK_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    logging.info("→ %d from %s", len(data), source)
    # annotate for later
    for art in data:
        art["source_name"] = source
    return data


def fetch_all_sources() -> list[dict]:
    all_articles = []
    for src in SOURCES:
        logging.info("🔎 Fetching from %s…", src)
        try:
            all_articles.extend(fetch_articles_from_source(src))
        except Exception as e:
            logging.error("✖ %s: %s", src, e)
    logging.info("✅ Fetched %d raw articles", len(all_articles))
    return all_articles
