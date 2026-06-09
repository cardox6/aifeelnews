import logging
from datetime import date

import requests

from app.config import config, settings
from app.jobs.mock_mediastack import fetch_mock_articles_from_source
from app.jobs.sources_list import SOURCES

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    # Single source of truth for "is production" (see config.security) so this
    # job and the OIDC gate can never disagree on what counts as production.
    return config.security.is_production


class MediastackAPIError(Exception):
    """Raised when Mediastack returns an inline error in an HTTP 200 response."""

    def __init__(self, code: int, error_type: str, message: str):
        self.code = code
        self.error_type = error_type
        super().__init__(f"Mediastack error {code} ({error_type}): {message}")


def fetch_articles_from_source(
    source: str,
    *,
    languages: str | None = None,
    fetch_date: str | None = None,
) -> list[dict]:
    """Fetch one source's articles from Mediastack.

    ``languages`` overrides ``settings.MEDIASTACK_LANGUAGES`` (e.g. ``"de"`` to
    fetch a single language) and ``fetch_date`` overrides today's date with a
    historical day (``"YYYY-MM-DD"``) — both used by the German backfill job to
    pull a specific language across past days. Defaults preserve the live path.
    """
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
        return fetch_mock_articles_from_source(
            source, languages or settings.MEDIASTACK_LANGUAGES
        )

    base_params = {
        "access_key": api_key,
        "sources": source,
        "languages": languages or settings.MEDIASTACK_LANGUAGES,
        "sort": settings.MEDIASTACK_SORT,
        "categories": settings.MEDIASTACK_FETCH_CATEGORIES,
        "limit": settings.MEDIASTACK_FETCH_LIMIT,
        "date": fetch_date or date.today().isoformat(),
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
        return fetch_mock_articles_from_source(
            source, languages or settings.MEDIASTACK_LANGUAGES
        )


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
