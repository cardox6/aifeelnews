"""Unit tests for the sentiment_magnitude backfill logic.

Exercises the pure ``backfill_magnitudes`` helper from the operator script
against the in-memory SQLite ``test_db`` fixture — no network, no real DB.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.sentiment_analysis import SentimentAnalysis
from app.models.source import Source
from scripts.dev.backfill_article_magnitude import backfill_magnitudes


def _seed(db: Session) -> None:
    db.add(Source(id=1, name="bbc"))
    db.flush()
    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)

    # Article 1: has two GCP-NL analyses — newest (by analyzed_at) wins.
    db.add(
        Article(
            id=1,
            source_id=1,
            title="GCP analysed",
            url="https://example.com/1",
            published_at=base,
            sentiment_label="positive",
            sentiment_score=0.8,
        )
    )
    db.add_all(
        [
            SentimentAnalysis(
                article_id=1,
                provider="GCP_NL",
                model_name="gcp_nl_v1",
                score=0.7,
                magnitude=1.1,  # older
                label="positive",
                analyzed_at=base - timedelta(days=2),
            ),
            SentimentAnalysis(
                article_id=1,
                provider="GCP_NL",
                model_name="gcp_nl_v1",
                score=0.8,
                magnitude=2.9,  # newer — this should win
                label="positive",
                analyzed_at=base,
            ),
        ]
    )

    # Article 2: VADER-only, no magnitude row → must stay NULL.
    db.add(
        Article(
            id=2,
            source_id=1,
            title="VADER only",
            url="https://example.com/2",
            published_at=base,
            sentiment_label="neutral",
            sentiment_score=0.0,
        )
    )
    db.add(
        SentimentAnalysis(
            article_id=2,
            provider="VADER",
            model_name=None,
            score=0.0,
            magnitude=None,
            label="neutral",
            analyzed_at=base,
        )
    )
    db.commit()


def test_backfill_copies_latest_gcp_magnitude(test_db: Session) -> None:
    _seed(test_db)

    updated = backfill_magnitudes(test_db, batch=10)

    assert updated == 1  # only article 1 changes
    a1 = test_db.get(Article, 1)
    a2 = test_db.get(Article, 2)
    assert a1 is not None and a1.sentiment_magnitude == 2.9  # newest GCP row
    assert a2 is not None and a2.sentiment_magnitude is None  # VADER stays null


def test_backfill_is_idempotent(test_db: Session) -> None:
    _seed(test_db)
    backfill_magnitudes(test_db, batch=10)

    # Second run touches nothing — values already match.
    updated = backfill_magnitudes(test_db, batch=10)
    assert updated == 0


def test_backfill_dry_run_writes_nothing(test_db: Session) -> None:
    _seed(test_db)

    updated = backfill_magnitudes(test_db, dry_run=True, batch=10)

    assert updated == 1  # reports the change...
    a1 = test_db.get(Article, 1)
    assert a1 is not None and a1.sentiment_magnitude is None  # ...but doesn't write
