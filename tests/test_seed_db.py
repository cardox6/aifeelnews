"""Tests for the local-development seed loader."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.article import Article
from app.models.article_category import ArticleCategory
from app.models.article_entity import ArticleEntity
from app.models.crawl_job import CrawlJob, CrawlStatus
from app.models.entity import Entity
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


# --------------------------------------------------------------------------- #
# Enrichment (sentiment_magnitude + entities + categories)
# --------------------------------------------------------------------------- #


def _enriched_payload() -> dict:
    """A small bilingual seed with magnitude + shared entities + categories.

    Two articles reference the SAME entity ("Donald Trump", PERSON) so the
    loader's global dedup is exercised: one Entity row, two ArticleEntity links.
    Dates are old on purpose so the recency anchor must shift them forward.
    """
    return {
        "_metadata": {"article_count": 2},
        "sources": [
            {"name": "bbc", "country": "gb", "language": "en"},
            {"name": "tagesschau", "country": "de", "language": "de"},
        ],
        "articles": [
            {
                "title": "EN headline",
                "description": "english body",
                "url": "https://example.com/en-1",
                "image_url": None,
                "published_at": "2025-01-01T12:00:00+00:00",
                "language": "en",
                "country": "gb",
                "category": "general",
                "sentiment_label": "positive",
                "sentiment_score": 0.4,
                "sentiment_magnitude": 9.2,
                "source_name": "bbc",
                "entities": [
                    {
                        "name": "Donald Trump",
                        "type": "PERSON",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/Donald_Trump",
                        "mid": "/m/0cqt90",
                        "salience": 0.8,
                        "mention_count": 3,
                        "analyzed_at": "2025-01-02T08:00:00+00:00",
                    }
                ],
                "categories": [
                    {
                        "name": "/News/Politics",
                        "confidence": 0.91,
                        "analyzed_at": "2025-01-02T08:00:00+00:00",
                    }
                ],
            },
            {
                "title": "DE headline",
                "description": "deutscher text",
                "url": "https://example.com/de-1",
                "image_url": None,
                "published_at": "2025-01-03T12:00:00+00:00",
                "language": "de",
                "country": "de",
                "category": "general",
                "sentiment_label": "negative",
                "sentiment_score": -0.3,
                "sentiment_magnitude": 14.7,
                "source_name": "tagesschau",
                "entities": [
                    {
                        "name": "Donald Trump",
                        "type": "PERSON",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/Donald_Trump",
                        "mid": "/m/0cqt90",
                        "salience": 0.5,
                        "mention_count": 1,
                        "analyzed_at": "2025-01-04T08:00:00+00:00",
                    }
                ],
                "categories": [],
            },
        ],
    }


@pytest.fixture()
def enriched_seed_file(tmp_path: Path) -> Path:
    path = tmp_path / "enriched_seed.json"
    path.write_text(json.dumps(_enriched_payload()), encoding="utf-8")
    return path


def test_seed_loads_magnitude(test_db, enriched_seed_file):
    """sentiment_magnitude is loaded onto the denormalized article column."""
    seed_database(test_db, json_path=enriched_seed_file)
    en = test_db.query(Article).filter_by(url="https://example.com/en-1").one()
    de = test_db.query(Article).filter_by(url="https://example.com/de-1").one()
    assert en.sentiment_magnitude == pytest.approx(9.2)
    assert de.sentiment_magnitude == pytest.approx(14.7)


def test_seed_dedupes_entities_and_links(test_db, enriched_seed_file):
    """The shared entity is created once; each article gets its own link."""
    summary = seed_database(test_db, json_path=enriched_seed_file)

    # One canonical entity, two mention links.
    assert summary["entities_inserted"] == 1
    assert summary["entity_links_inserted"] == 2
    assert test_db.query(Entity).count() == 1
    assert test_db.query(ArticleEntity).count() == 2

    entity = test_db.query(Entity).one()
    assert entity.name == "Donald Trump"
    assert entity.wikipedia_url is not None  # survives the chart quality gate


def test_seed_loads_categories(test_db, enriched_seed_file):
    """Categories are attached to the right article."""
    summary = seed_database(test_db, json_path=enriched_seed_file)
    assert summary["categories_inserted"] == 1
    cat = test_db.query(ArticleCategory).one()
    en = test_db.query(Article).filter_by(url="https://example.com/en-1").one()
    assert cat.article_id == en.id
    assert cat.name == "/News/Politics"


def test_seed_shifts_analyzed_at_with_recency_anchor(test_db, enriched_seed_file):
    """analyzed_at is shifted by the same offset as published_at.

    The momentum / trending-names windows key off analyzed_at, so it must move
    forward with the article dates — otherwise the seeded mentions fall outside
    the recent window and the charts read empty.
    """
    seed_database(test_db, json_path=enriched_seed_file)

    # Newest published_at in the fixture is 2025-01-03; anchored to ~1 day ago.
    en = test_db.query(Article).filter_by(url="https://example.com/en-1").one()
    link = test_db.query(ArticleEntity).filter_by(article_id=en.id).one()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # analyzed_at (orig 2025-01-02) should now be recent, not 2025.
    assert link.analyzed_at > now - timedelta(days=40)
    # And it stays BEFORE now (pipeline can't analyze the future).
    assert link.analyzed_at <= now


def test_seed_literal_dates_keeps_original_analyzed_at(test_db, enriched_seed_file):
    """With anchor_recent=False, analyzed_at keeps its literal snapshot value."""
    seed_database(test_db, json_path=enriched_seed_file, anchor_recent=False)
    en = test_db.query(Article).filter_by(url="https://example.com/en-1").one()
    link = test_db.query(ArticleEntity).filter_by(article_id=en.id).one()
    assert link.analyzed_at == datetime(2025, 1, 2, 8, 0, 0)


def test_seed_reset_sweeps_orphaned_entities(test_db, enriched_seed_file):
    """--reset removes articles, links, categories AND now-orphaned entities."""
    seed_database(test_db, json_path=enriched_seed_file)
    assert test_db.query(Entity).count() == 1

    # Reset + reload: should not accumulate duplicate entities/links.
    seed_database(test_db, json_path=enriched_seed_file, reset=True)
    assert test_db.query(Article).count() == 2
    assert test_db.query(Entity).count() == 1
    assert test_db.query(ArticleEntity).count() == 2
    assert test_db.query(ArticleCategory).count() == 1


def test_seed_enrichment_is_idempotent(test_db, enriched_seed_file):
    """Re-running without --reset adds no duplicate links or entities."""
    seed_database(test_db, json_path=enriched_seed_file)
    second = seed_database(test_db, json_path=enriched_seed_file)
    assert second["articles_inserted"] == 0
    assert second["entities_inserted"] == 0
    assert second["entity_links_inserted"] == 0
    assert second["categories_inserted"] == 0
    assert test_db.query(Entity).count() == 1
    assert test_db.query(ArticleEntity).count() == 2
    assert test_db.query(ArticleCategory).count() == 1
