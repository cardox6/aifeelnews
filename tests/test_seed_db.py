"""Tests for the local-development seed loader."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.models.article import Article
from app.models.crawl_job import CrawlJob, CrawlStatus
from app.models.source import Source
from app.seeds.seed_db import DEFAULT_SEED_PATH, seed_database


@pytest.fixture()
def seed_payload() -> dict:
    with DEFAULT_SEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def test_seed_loads_articles_and_sources(test_db, seed_payload):
    """First seed run inserts every source + article from the JSON."""
    summary = seed_database(test_db)

    expected_sources = len(seed_payload["sources"])
    expected_articles = len(seed_payload["articles"])

    assert summary["sources_inserted"] == expected_sources
    assert summary["articles_inserted"] == expected_articles
    assert summary["sources_skipped"] == 0

    assert test_db.query(Source).count() == expected_sources
    assert test_db.query(Article).count() == expected_articles

    # Spot-check a row to confirm field mapping is correct.
    first = seed_payload["articles"][0]
    fetched = test_db.query(Article).filter_by(url=first["url"]).one()
    assert fetched.title == first["title"]
    assert fetched.sentiment_label == first["sentiment_label"]
    assert fetched.source.name == first["source_name"]


def test_seed_is_idempotent(test_db, seed_payload):
    """Running the seed twice inserts zero new rows on the second pass."""
    seed_database(test_db)
    second = seed_database(test_db)

    assert second["sources_inserted"] == 0
    assert second["articles_inserted"] == 0
    assert second["sources_skipped"] == len(seed_payload["sources"])
    assert second["articles_skipped"] == len(seed_payload["articles"])

    # Counts unchanged.
    assert test_db.query(Source).count() == len(seed_payload["sources"])
    assert test_db.query(Article).count() == len(seed_payload["articles"])


def test_seed_skips_duplicate_urls_within_batch(test_db, seed_payload):
    """Pre-existing rows are kept; remaining rows are still inserted cleanly."""
    # Insert one article (and its source) by hand, mirroring the first JSON row.
    first = seed_payload["articles"][0]
    src_name = first["source_name"]
    pre_source = Source(name=src_name)
    test_db.add(pre_source)
    test_db.flush()

    pre_published = datetime.fromisoformat(
        first["published_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None)
    pre_article = Article(
        title="Existing title — not the seed",
        description=first["description"],
        url=first["url"],
        image_url=first["image_url"],
        published_at=pre_published,
        language=first["language"],
        country=first["country"],
        category=first["category"],
        sentiment_label=first["sentiment_label"],
        sentiment_score=first["sentiment_score"],
        source_id=pre_source.id,
    )
    test_db.add(pre_article)
    test_db.commit()

    summary = seed_database(test_db, json_path=Path(DEFAULT_SEED_PATH))

    # The pre-existing article must remain unchanged (not overwritten).
    refetched = test_db.query(Article).filter_by(url=first["url"]).one()
    assert refetched.title == "Existing title — not the seed"

    # All other articles should have been inserted; total = full seed size.
    assert test_db.query(Article).count() == len(seed_payload["articles"])
    assert summary["articles_skipped"] >= 1
    assert summary["articles_inserted"] == len(seed_payload["articles"]) - 1


def test_seed_queue_crawl_jobs_off_by_default(test_db, seed_payload):
    """Without the flag, no crawl_jobs rows are created."""
    summary = seed_database(test_db)
    assert summary["crawl_jobs_inserted"] == 0
    assert test_db.query(CrawlJob).count() == 0


def test_seed_queue_crawl_jobs_enqueues_pending(test_db, seed_payload):
    """With ``queue_crawl_jobs=True``, one PENDING job is enqueued per article."""
    summary = seed_database(test_db, queue_crawl_jobs=True)
    expected = len(seed_payload["articles"])
    assert summary["crawl_jobs_inserted"] == expected
    assert test_db.query(CrawlJob).count() == expected
    # All freshly enqueued, none picked up yet.
    assert (
        test_db.query(CrawlJob).filter(CrawlJob.status == CrawlStatus.PENDING).count()
        == expected
    )


def test_seed_queue_crawl_jobs_skips_articles_with_existing_jobs(test_db, seed_payload):
    """Re-running with the flag does not duplicate jobs for already-queued articles."""
    seed_database(test_db, queue_crawl_jobs=True)
    second = seed_database(test_db, queue_crawl_jobs=True)
    # Articles already had jobs from the first run — second run enqueues nothing.
    assert second["crawl_jobs_inserted"] == 0
    assert test_db.query(CrawlJob).count() == len(seed_payload["articles"])
