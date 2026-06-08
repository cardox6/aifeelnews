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
