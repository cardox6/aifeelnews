"""Backfill German articles from Mediastack history into Postgres + NLP.

Gives the German feed and the EN/DE dashboard ~30 days of history on day one,
instead of a slowly-filling empty line. This is the *upstream* counterpart to
``app/jobs/backfill_bigquery.py`` (which streams already-analyzed Postgres rows
into BigQuery): here we fetch historical Mediastack articles, normalize + ingest
them with ``language="de"``, and run the existing crawl worker so each gets full
GCP NL analysis (sentiment + entities + V2-model categories).

It reuses the live pipeline functions (``fetch_articles_from_source`` →
``normalize_articles`` → ``ingest_articles`` → ``run_crawl_worker``) so there is
no duplicated fetch/NLP logic and ingest's URL-unique dedup makes re-runs
idempotent. Volume is bounded by a per-source/day cap to keep GCP NL spend
predictable.

Usage:
    python -m app.jobs.backfill_german                 # 30 days, full NLP
    python -m app.jobs.backfill_german --dry-run        # count only, no fetch
    python -m app.jobs.backfill_german --days=7         # shorter window
    python -m app.jobs.backfill_german --per-source-cap=5
    python -m app.jobs.backfill_german --no-crawl       # ingest only, skip NLP crawl
"""

import logging
import sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.jobs.crawl_worker import run_crawl_worker
from app.jobs.fetch_from_mediastack import fetch_articles_from_source
from app.jobs.ingest_articles import ingest_articles
from app.jobs.normalize_articles import normalize_articles
from app.jobs.sources_list import GERMAN_SOURCES
from app.utils.logging import setup_logging

setup_logging()
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

DEFAULT_DAYS = 30
DEFAULT_PER_SOURCE_CAP = 8


def _historical_days(days: int) -> list[str]:
    """ISO ``YYYY-MM-DD`` strings for the last ``days`` days, oldest first."""
    today = date.today()
    return [(today - timedelta(days=n)).isoformat() for n in range(days, 0, -1)]


def backfill_german(
    *,
    days: int = DEFAULT_DAYS,
    per_source_cap: int = DEFAULT_PER_SOURCE_CAP,
    include_crawling: bool = True,
    dry_run: bool = False,
) -> int:
    """Backfill German articles over the last ``days`` days.

    Returns the number of new articles ingested (0 on a dry run).
    """
    logger.info(
        "=== German backfill: days=%d, per_source_cap=%d, crawl=%s, dry_run=%s ===",
        days,
        per_source_cap,
        include_crawling,
        dry_run,
    )

    raw: list[dict] = []
    for day in _historical_days(days):
        day_total = 0
        for source in GERMAN_SOURCES:
            if dry_run:
                # Don't hit the API on a dry run — just show the plan.
                continue
            articles = fetch_articles_from_source(
                source, languages="de", fetch_date=day
            )
            # Cap per source per day to bound GCP NL cost downstream. Log the
            # drop so the trimmed volume is explicit (never a silent truncation).
            if len(articles) > per_source_cap:
                logger.info(
                    "  %s %s: capping %d -> %d articles",
                    day,
                    source,
                    len(articles),
                    per_source_cap,
                )
                articles = articles[:per_source_cap]
            raw.extend(articles)
            day_total += len(articles)
        logger.info(
            "%s: %d articles across %d sources", day, day_total, len(GERMAN_SOURCES)
        )

    if dry_run:
        planned = days * len(GERMAN_SOURCES) * per_source_cap
        logger.info(
            "DRY RUN — would fetch up to %d articles (%d days x %d sources x cap %d)",
            planned,
            days,
            len(GERMAN_SOURCES),
            per_source_cap,
        )
        return 0

    logger.info("Fetched %d raw German articles; normalizing…", len(raw))
    norm = normalize_articles(raw)
    logger.info("Normalized to %d articles; ingesting…", len(norm))

    db = SessionLocal()
    try:
        new = ingest_articles(db, norm)
        logger.info("Ingested %d new German articles", new)
    finally:
        db.close()

    if include_crawling and new > 0:
        # Drain the crawl queue so the freshly-ingested German articles get full
        # GCP NL analysis. Cap generously — one job per new article plus slack.
        max_jobs = new + 10
        logger.info("Running crawl worker (max_jobs=%d) for full NLP…", max_jobs)
        result = run_crawl_worker(max_jobs=max_jobs)
        logger.info(
            "Crawl complete: %d successful, %d failed",
            result["successful"],
            result["failed"],
        )
    elif include_crawling:
        logger.info("No new articles — skipping crawl.")

    logger.info("=== German backfill complete: %d new articles ===", new)
    return new


def _parse_args(argv: list[str]) -> dict:
    opts: dict = {
        "days": DEFAULT_DAYS,
        "per_source_cap": DEFAULT_PER_SOURCE_CAP,
        "include_crawling": True,
        "dry_run": False,
    }
    for arg in argv:
        if arg == "--dry-run":
            opts["dry_run"] = True
        elif arg == "--no-crawl":
            opts["include_crawling"] = False
        elif arg.startswith("--days="):
            opts["days"] = int(arg.split("=", 1)[1])
        elif arg.startswith("--per-source-cap="):
            opts["per_source_cap"] = int(arg.split("=", 1)[1])
    return opts


if __name__ == "__main__":
    backfill_german(**_parse_args(sys.argv[1:]))
