#!/usr/bin/env python3
"""Backfill ``articles.sentiment_magnitude`` from historical GCP-NL analyses.

The new denormalized ``Article.sentiment_magnitude`` column is populated going
forward by the crawl worker, but pre-existing articles have it NULL. This
one-off operator script copies the magnitude from each article's most recent
GCP-NL ``SentimentAnalysis`` row (the only provider that produces magnitude)
onto the article.

VADER-only articles have no magnitude row, so they are skipped and stay NULL —
the frontend degrades gracefully on a null magnitude. This means the script is
effectively a no-op against a VADER-only local seed; it only does real work
against a database that has been through the GCP-NL pipeline (i.e. production).

Usage:
    python scripts/dev/backfill_article_magnitude.py            # apply
    python scripts/dev/backfill_article_magnitude.py --dry-run  # report only
    python scripts/dev/backfill_article_magnitude.py --batch 500

Idempotent: re-running only re-touches articles whose magnitude differs from
their latest GCP-NL row, so a second run after a clean first run updates nothing.
Operator tool, not part of the test suite (the backfill logic is unit-tested in
tests/test_backfill_magnitude.py against an in-memory DB).
"""

import argparse
import os
import sys

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.article import Article
from app.models.sentiment_analysis import SentimentAnalysis


def backfill_magnitudes(db: Session, *, dry_run: bool = False, batch: int = 500) -> int:
    """Copy the latest GCP-NL magnitude onto each article. Returns rows updated.

    Pure of any CLI/printing concerns so it can be unit-tested directly.
    """
    updated = 0
    offset = 0
    while True:
        articles = (
            db.query(Article).order_by(Article.id).offset(offset).limit(batch).all()
        )
        if not articles:
            break
        for article in articles:
            latest = (
                db.query(SentimentAnalysis)
                .filter(SentimentAnalysis.article_id == article.id)
                .filter(SentimentAnalysis.magnitude.isnot(None))
                .order_by(SentimentAnalysis.analyzed_at.desc())
                .first()
            )
            if latest is None:
                continue  # VADER-only / no magnitude — leave NULL
            if article.sentiment_magnitude != latest.magnitude:
                if not dry_run:
                    article.sentiment_magnitude = latest.magnitude
                updated += 1
        offset += batch
    if not dry_run:
        db.commit()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill articles.sentiment_magnitude from GCP-NL analyses"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many rows would change without writing",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=500,
        help="Articles per query batch (default: 500)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        updated = backfill_magnitudes(db, dry_run=args.dry_run, batch=args.batch)
        verb = "would update" if args.dry_run else "updated"
        print(f"sentiment_magnitude backfill: {verb} {updated} article(s).")
        if updated == 0:
            print(
                "No GCP-NL magnitude rows found to copy "
                "(expected against a VADER-only seed)."
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
