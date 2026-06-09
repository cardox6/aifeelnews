"""Exercise the advanced-SQL analytics in app/crud/analytics.py — window
functions, CTEs, RANK() and GROUPING SETS — against a real Postgres backend.

These are the most complex and most regression-prone queries in the repo and
the showcase for the Relational Databases work, but they were previously
untested (SQLite can't run GROUPING SETS / RANK() OVER / STDDEV). Postgres-only:
skipped when no TEST_POSTGRES_URL is set.
"""

from __future__ import annotations

import pytest

from app.crud.analytics import (
    daily_category_sentiment_pivot,
    entity_momentum,
    sentiment_grouping_sets,
    sentiment_rolling_average,
    source_sentiment_ranked,
)
from app.models.article import Article
from app.seeds.seed_db import seed_database

pytestmark = pytest.mark.postgres

# Seed articles are all >30 days old; use a wide window so the cutoff includes
# them (every crud function filters published_at >= now() - days).
WIDE_DAYS = 3650


@pytest.fixture()
def seeded(postgres_db):
    seed_database(postgres_db)  # commits
    return postgres_db


def test_rolling_average_is_smoothed_window(seeded):
    rows = sentiment_rolling_average(seeded, days=WIDE_DAYS, window=7)
    assert rows, "rolling average returned no rows"
    # Each row carries the day's avg plus the windowed rolling avg.
    first = rows[0]
    assert {"day", "article_count", "avg_sentiment", "rolling_avg"} <= set(first)
    # The first row's rolling avg equals its own daily avg (no preceding rows).
    assert float(first["rolling_avg"]) == pytest.approx(
        float(first["avg_sentiment"]), abs=1e-4
    )


def test_source_ranked_is_descending_by_sentiment(seeded):
    rows = source_sentiment_ranked(seeded, days=WIDE_DAYS)
    assert rows, "source ranking returned no rows (need >=3 articles/source)"
    # RANK() assigns 1 to the most positive source; ranks are non-decreasing
    # and avg_sentiment is non-increasing down the list.
    assert rows[0]["positivity_rank"] == 1
    ranks = [r["positivity_rank"] for r in rows]
    assert ranks == sorted(ranks)
    sentiments = [float(r["avg_sentiment"]) for r in rows]
    assert sentiments == sorted(sentiments, reverse=True)


def test_grouping_sets_has_grand_total_row(seeded):
    rows = sentiment_grouping_sets(seeded, days=WIDE_DAYS)
    assert rows
    # The grand-total row has both grouping flags set and aggregates everything.
    grand = [
        r for r in rows if r["is_category_total"] == 1 and r["is_label_total"] == 1
    ]
    assert len(grand) == 1, "expected exactly one grand-total row"
    total = grand[0]["article_count"]
    # Per-label subtotals (label present, category rolled up) must sum to the
    # grand total.
    label_subtotals = [
        r["article_count"]
        for r in rows
        if r["is_category_total"] == 1 and r["is_label_total"] == 0
    ]
    assert sum(label_subtotals) == total


def test_entity_momentum_runs_and_returns_expected_shape(seeded):
    """entity_momentum (FULL OUTER JOIN + CASE growth_pct over two windows) is
    one of the two most complex Postgres-only queries and was untested. The
    seed creates no entities, so the result is legitimately empty — but the
    query must still EXECUTE without error and return the documented columns
    when rows exist. A broken FULL OUTER JOIN / CASE / cast would raise here."""
    rows = entity_momentum(seeded, days=14)
    assert isinstance(rows, list)
    for r in rows:  # only iterates if entities were present
        assert {
            "entity_name",
            "entity_type",
            "recent_mentions",
            "previous_mentions",
            "growth_pct",
        } <= set(r)


def test_entity_momentum_keys_off_analyzed_at_not_published_at(seeded):
    """Regression: the momentum windows must key off article_entities.analyzed_at,
    not articles.published_at. Entity enrichment lags publication (the worker
    drains a backlog), so an article published weeks ago can be entity-analyzed
    today. Here every article is OLD by published_at but the entity mentions are
    RECENT by analyzed_at — the chart must still surface them. Before the fix
    this returned [] (empty 'trending names')."""
    from datetime import datetime, timedelta, timezone

    from app.models.article_entity import ArticleEntity
    from app.models.entity import Entity

    now = datetime.now(timezone.utc)
    # Pick three seeded articles (all published >30d ago).
    article_ids = [a.id for a in seeded.query(Article).limit(3).all()]
    assert len(article_ids) == 3, "seed should provide >=3 articles"

    # wikipedia_url is set so the entity passes the quality gate (only
    # Knowledge-Graph-resolved entities are surfaced).
    ent = Entity(
        name="Test Trending Name",
        type="PERSON",
        wikipedia_url="https://en.wikipedia.org/wiki/Test",
    )
    seeded.add(ent)
    seeded.flush()

    # article_entities is UNIQUE(article_id, entity_id), so one row per article.
    # Two distinct articles land in the recent window, one in the previous —
    # recent=2 vs previous=1, a clear upward trend. analyzed_at is recent even
    # though the underlying articles were published long ago.
    seeded.add_all(
        [
            ArticleEntity(
                article_id=article_ids[0],
                entity_id=ent.id,
                salience=0.5,
                mention_count=1,
                analyzed_at=now - timedelta(days=1),  # recent window
            ),
            ArticleEntity(
                article_id=article_ids[1],
                entity_id=ent.id,
                salience=0.5,
                mention_count=1,
                analyzed_at=now - timedelta(days=2),  # recent window
            ),
            ArticleEntity(
                article_id=article_ids[2],
                entity_id=ent.id,
                salience=0.5,
                mention_count=1,
                analyzed_at=now - timedelta(days=10),  # previous window
            ),
        ]
    )
    seeded.commit()

    rows = entity_momentum(seeded, days=14)
    names = {r["entity_name"] for r in rows}
    assert "Test Trending Name" in names, (
        "momentum must surface an entity with recent analyzed_at even when the "
        "underlying articles were published long ago"
    )
    hit = next(r for r in rows if r["entity_name"] == "Test Trending Name")
    assert hit["recent_mentions"] == 2
    assert hit["previous_mentions"] == 1


def test_entity_momentum_excludes_low_quality_and_publishers(seeded):
    """The momentum query applies the shared entity quality gate: drop entities
    with no wikipedia_url (generic common nouns like 'markets') and publisher /
    wire-service names (BBC, Getty) even though those are real orgs with a
    wikipedia_url. Only the genuine subject entity should survive."""
    from datetime import datetime, timedelta, timezone

    from app.models.article_entity import ArticleEntity
    from app.models.entity import Entity

    now = datetime.now(timezone.utc)
    article_ids = [a.id for a in seeded.query(Article).limit(3).all()]
    assert len(article_ids) == 3

    real = Entity(
        name="Real Subject",
        type="PERSON",
        wikipedia_url="https://en.wikipedia.org/wiki/Real",
    )
    # Generic common noun: GCP NL gives it no wikipedia_url → excluded by the gate.
    generic = Entity(name="markets", type="OTHER", wikipedia_url=None)
    # Publisher: a real org WITH a wikipedia_url → excluded only by the denylist.
    publisher = Entity(
        name="BBC",
        type="ORGANIZATION",
        wikipedia_url="https://en.wikipedia.org/wiki/BBC",
    )
    seeded.add_all([real, generic, publisher])
    seeded.flush()

    # Give all three plenty of recent mentions (well over the >=3 threshold).
    for ent in (real, generic, publisher):
        for art_id in article_ids:
            seeded.add(
                ArticleEntity(
                    article_id=art_id,
                    entity_id=ent.id,
                    salience=0.5,
                    mention_count=1,
                    analyzed_at=now - timedelta(days=1),
                )
            )
    seeded.commit()

    names = {r["entity_name"] for r in entity_momentum(seeded, days=14)}
    assert "Real Subject" in names
    assert "markets" not in names  # no wikipedia_url
    assert "BBC" not in names  # publisher denylist


def test_daily_category_pivot_cumulative_is_monotonic(seeded):
    """daily_category_sentiment_pivot uses SUM() OVER (PARTITION BY category
    ORDER BY day) for a running total. Within each category the cumulative
    count must be non-decreasing by day and end at that category's total."""
    rows = daily_category_sentiment_pivot(seeded, days=WIDE_DAYS)
    assert rows, "pivot returned no rows (seed sets sentiment_score)"
    assert {
        "day",
        "category",
        "article_count",
        "avg_sentiment",
        "cumulative_articles",
    } <= set(rows[0])

    by_category: dict[str, list[dict]] = {}
    for r in rows:
        by_category.setdefault(r["category"], []).append(r)
    for cat_rows in by_category.values():
        cumulative = [int(r["cumulative_articles"]) for r in cat_rows]
        assert cumulative == sorted(cumulative), "cumulative must be monotonic"
        assert cumulative[-1] == sum(int(r["article_count"]) for r in cat_rows)
