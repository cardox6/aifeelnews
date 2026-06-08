"""Exercise the PostgreSQL views and stored functions from migration
e1f2a3b4c5d6 (fn fix a1b2c3d4e5f6).

Postgres-only: these objects use CREATE VIEW ... FILTER, PL/pgSQL functions
and GROUPING-SETS-adjacent SQL that SQLite cannot run, so every test is
@pytest.mark.postgres and skips when no TEST_POSTGRES_URL is set
(see conftest.pytest_collection_modifyitems).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.seeds.seed_db import seed_database

pytestmark = pytest.mark.postgres

# Seed articles span 2026-01-14..2026-05-03 (all well over 30 days old), so the
# functions' default 30-day window would return zero rows. Use a wide window.
WIDE_DAYS = 3650


@pytest.fixture()
def seeded(postgres_db):
    """Load the bundled seed dataset so the views have rows behind them."""
    seed_database(postgres_db)  # commits
    return postgres_db


class TestViews:
    def test_v_article_summary_joins_source_name(self, seeded):
        rows = seeded.execute(
            text(
                "SELECT article_id, title, source_name, sentiment_label "
                "FROM v_article_summary LIMIT 5"
            )
        ).fetchall()
        assert rows, "v_article_summary returned no rows after seeding"
        assert all(r.source_name for r in rows)

    def test_v_source_stats_aggregates_counts(self, seeded):
        rows = seeded.execute(
            text(
                "SELECT source_name, article_count, avg_sentiment "
                "FROM v_source_stats ORDER BY article_count DESC"
            )
        ).fetchall()
        assert rows
        assert sum(r.article_count for r in rows) >= 1

    def test_v_daily_sentiment_buckets_by_day(self, seeded):
        rows = seeded.execute(
            text(
                "SELECT day, article_count, positive_count, negative_count, "
                "neutral_count FROM v_daily_sentiment"
            )
        ).fetchall()
        assert rows
        # Seed labels are all in {positive, negative, neutral}, so per-day the
        # three bucket counts must sum to the article_count for that day.
        for r in rows:
            assert r.article_count == (
                r.positive_count + r.negative_count + r.neutral_count
            )

    def test_v_trending_entities_is_queryable(self, seeded):
        # Seed JSON has no entities and the view filters to the last 7 days, so
        # an empty result set is expected — this proves the view DDL is sound.
        rows = seeded.execute(
            text(
                "SELECT entity_id, entity_name, total_mentions FROM v_trending_entities"
            )
        ).fetchall()
        assert isinstance(rows, list)


class TestStoredFunctions:
    def test_fn_sentiment_distribution_returns_percentages(self, seeded):
        # Regression guard for a1b2c3d4e5f6: the pre-fix definition raised
        # 'column reference "sentiment_label" is ambiguous'. Success here proves
        # the migration chain actually ran (not create_all).
        rows = seeded.execute(
            text(
                "SELECT sentiment_label, article_count, percentage "
                f"FROM fn_sentiment_distribution({WIDE_DAYS})"
            )
        ).fetchall()
        assert rows, "fn_sentiment_distribution returned no rows"
        total_pct = sum(float(r.percentage) for r in rows)
        assert 99.0 <= total_pct <= 101.0  # rounding tolerance

    def test_fn_source_performance_returns_rows(self, seeded):
        rows = seeded.execute(
            text(
                "SELECT source_name, article_count, avg_sentiment, "
                "entity_richness, crawl_success_rate "
                f"FROM fn_source_performance({WIDE_DAYS})"
            )
        ).fetchall()
        assert rows
        assert all(r.article_count >= 1 for r in rows)
