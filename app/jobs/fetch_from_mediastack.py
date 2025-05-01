import requests
import logging
from datetime import date
from app.config import settings
from app.jobs.sources_list import SOURCES


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
