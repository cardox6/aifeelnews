import logging
import os
from datetime import date

import requests

from app.config import settings
from app.jobs.mock_mediastack import fetch_mock_articles_from_source
from app.jobs.sources_list import SOURCES

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    return os.getenv("ENV", "local") in ("production", "prod")


class MediastackAPIError(Exception):
    """Raised when Mediastack returns an inline error in an HTTP 200 response."""

    def __init__(self, code: int, error_type: str, message: str):
        self.code = code
        self.error_type = error_type
        super().__init__(f"Mediastack error {code} ({error_type}): {message}")


def fetch_articles_from_source(source: str) -> list[dict]:
    api_key = settings.MEDIASTACK_API_KEY

    if not api_key:
        if _is_production():
            logger.error(
                "MEDIASTACK_API_KEY is empty — skipping %s. "
                "Check Secret Manager and Cloud Run env vars.",
                source,
            )
            return []
        logger.info("MEDIASTACK_API_KEY not set — using mock data for %s", source)
        return fetch_mock_articles_from_source(source)

    base_params = {
        "access_key": api_key,
        "sources": source,
        "languages": settings.MEDIASTACK_LANGUAGES,
        "sort": settings.MEDIASTACK_SORT,
        "categories": settings.MEDIASTACK_FETCH_CATEGORIES,
        "limit": settings.MEDIASTACK_FETCH_LIMIT,
        "date": date.today().isoformat(),
    }

    try:
        resp = requests.get(
            settings.MEDIASTACK_BASE_URL,
            params=base_params,  # type: ignore[arg-type]
            timeout=settings.MEDIASTACK_TIMEOUT,
        )
        resp.raise_for_status()

        body = resp.json()

        # Mediastack returns HTTP 200 with inline error JSON for bad keys, etc.
        if "error" in body:
            err = body["error"]
            raise MediastackAPIError(
                code=err.get("code", 0),
                error_type=err.get("type", "unknown"),
                message=err.get("info", "No details"),
            )

        data = body.get("data", [])
        logger.info("-> %d from %s", len(data), source)
        if data:
            sample = data[0]
            logger.debug(
                "   sample: published=%s url=%s",
                sample.get("published_at", "?"),
                (sample.get("url") or "?")[:120],
            )

        for art in data:
            art["source_name"] = source
        return data  # type: ignore[no-any-return]

    except MediastackAPIError as e:
        logger.error("Mediastack API error for %s: %s", source, e, exc_info=True)
        return []

    except (requests.RequestException, requests.HTTPError) as e:
        if _is_production():
            logger.error(
                "Mediastack request failed for %s: %s", source, e, exc_info=True
            )
            return []
        logger.warning(
            "Mediastack request failed for %s: %s — using mock data", source, e
        )
        return fetch_mock_articles_from_source(source)


def fetch_all_sources() -> list[dict]:
    api_key = settings.MEDIASTACK_API_KEY
    logger.info(
        "Starting fetch for %d sources [env=%s, api_key=%s]",
        len(SOURCES),
        "production" if _is_production() else "development",
        "SET" if api_key else "EMPTY",
    )

    all_articles: list[dict] = []
    real_count = 0
    mock_count = 0

    for src in SOURCES:
        try:
            articles = fetch_articles_from_source(src)
            all_articles.extend(articles)

            if articles and "example.com" in articles[0].get("url", ""):
                mock_count += 1
            elif articles:
                real_count += 1
        except Exception as e:
            logger.error("Unexpected error fetching %s: %s", src, e, exc_info=True)

    empty_count = len(SOURCES) - real_count - mock_count
    logger.info(
        "Fetched %d raw articles from %d sources (%d real, %d mock, %d empty)",
        len(all_articles),
        len(SOURCES),
        real_count,
        mock_count,
        empty_count,
    )

    if mock_count > 0 and _is_production():
        logger.warning(
            "%d sources returned mock data in production — this should not happen",
            mock_count,
        )

    return all_articles
