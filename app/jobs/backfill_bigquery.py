"""
Backfill BigQuery from existing PostgreSQL data.

Streams sentiment_events, entity_events, and category_events from
PostgreSQL into BigQuery. Idempotent via event_id pre-check.

Usage:
    python -m app.jobs.backfill_bigquery                    # backfill all
    python -m app.jobs.backfill_bigquery --dry-run           # preview only
    python -m app.jobs.backfill_bigquery --since=2025-06-01  # partial
    python -m app.jobs.backfill_bigquery --sentiment-only    # skip entities/categories
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.config import config
from app.database import SessionLocal
from app.models.article import Article
from app.models.article_category import ArticleCategory
from app.models.article_content import ArticleContent
from app.models.article_entity import ArticleEntity
from app.models.entity import Entity
from app.models.sentiment_analysis import SentimentAnalysis
from app.models.source import Source
from app.utils.logging import setup_logging

# Use the central structured-logging setup so standalone backfill runs
# emit the same Cloud-Logging-friendly JSON as the web app.
setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_existing_event_ids(table_id: str) -> Set[str]:
    """Query BigQuery for event_ids already present in a table."""
    try:
        from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

        from app.services.bigquery import _get_client, _table_fqn

        fqn = _table_fqn(table_id)
        query = f"SELECT DISTINCT event_id FROM {fqn}"
        results = _get_client().query(query, job_config=bigquery.QueryJobConfig())
        return {row["event_id"] for row in results}
    except Exception as e:
        logger.warning("Could not fetch existing IDs from %s: %s", table_id, e)
        return set()


def _batch_insert(bq_rows: List[Dict[str, Any]], table_id: str) -> int:
    """Insert rows into BigQuery in batches of 500. Returns rows inserted."""
    if not bq_rows:
        return 0

    from app.services.bigquery import _ensure_tables, _get_client

    _ensure_tables()
    client = _get_client()
    cfg = config.bigquery
    table = client.get_table(client.dataset(cfg.dataset_id).table(table_id))

    inserted = 0
    for i in range(0, len(bq_rows), 500):
        batch = bq_rows[i : i + 500]
        errors = client.insert_rows_json(table, batch)
        if errors:
            logger.error("Insert errors (batch %d): %s", i, errors)
        else:
            inserted += len(batch)
            logger.info(
                "  Batch %d-%d (%d/%d)", i + 1, i + len(batch), inserted, len(bq_rows)
            )
    return inserted


# ---------------------------------------------------------------------------
# Sentiment backfill
# ---------------------------------------------------------------------------


def backfill_sentiment_events(
    dry_run: bool = False, since: Optional[datetime] = None
) -> int:
    logger.info("\n=== Backfilling sentiment_events ===")
    if not config.bigquery.enable_bigquery and not dry_run:
        logger.error(
            "BigQuery disabled. Set BIGQUERY_ENABLE_BIGQUERY=true or use --dry-run"
        )
        return 0

    db = SessionLocal()
    try:
        query = (
            db.query(
                SentimentAnalysis.article_id,
                Article.url.label("article_url"),
                Article.title.label("article_title"),
                Source.name.label("source_name"),
                Article.published_at,
                SentimentAnalysis.analyzed_at.label("ingested_at"),
                SentimentAnalysis.provider.label("sentiment_provider"),
                SentimentAnalysis.model_name.label("sentiment_model"),
                SentimentAnalysis.score.label("sentiment_score"),
                SentimentAnalysis.magnitude.label("sentiment_magnitude"),
                SentimentAnalysis.label.label("sentiment_label"),
                SentimentAnalysis.language,
                Article.country,
                Article.category,
                ArticleContent.content_length,
            )
            .join(Article, SentimentAnalysis.article_id == Article.id)
            .join(Source, Article.source_id == Source.id)
            .outerjoin(ArticleContent, Article.id == ArticleContent.article_id)
        )
        if since:
            query = query.filter(SentimentAnalysis.analyzed_at >= since)

        rows = query.order_by(SentimentAnalysis.analyzed_at.asc()).all()
        logger.info("Found %d sentiment analyses in PostgreSQL", len(rows))
        if not rows:
            return 0

        existing_ids = (
            set()
            if dry_run
            else _get_existing_event_ids(config.bigquery.sentiment_table)
        )
        if existing_ids:
            logger.info("Found %d existing event IDs in BigQuery", len(existing_ids))

        bq_rows: List[Dict[str, Any]] = []
        provider_counts: Dict[str, int] = {}
        skipped = 0

        for row in rows:
            provider = row.sentiment_provider or "VADER"
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            event_id = f"{row.article_id}_{provider}_{int(row.ingested_at.timestamp())}"

            if event_id in existing_ids:
                skipped += 1
                continue

            bq_rows.append(
                {
                    "event_id": event_id,
                    "article_id": row.article_id,
                    "article_url": row.article_url,
                    "article_title": row.article_title,
                    "source_name": row.source_name,
                    "published_at": row.published_at.isoformat()
                    if row.published_at
                    else None,
                    "ingested_at": row.ingested_at.isoformat()
                    if row.ingested_at
                    else None,
                    "sentiment_provider": provider,
                    "sentiment_model": row.sentiment_model or "",
                    "sentiment_score": row.sentiment_score,
                    "sentiment_magnitude": row.sentiment_magnitude,
                    "sentiment_label": row.sentiment_label,
                    "confidence": None,
                    "language": row.language,
                    "country": row.country,
                    "category": row.category,
                    "content_length": row.content_length,
                    "processing_time_ms": None,
                    "extraction_method": "backfill_gcpnl"
                    if provider == "GCP_NL"
                    else "backfill_vader",
                }
            )

        logger.info(
            "Providers: %s | Skipped: %d | To insert: %d",
            provider_counts,
            skipped,
            len(bq_rows),
        )

        if dry_run:
            for r in bq_rows[:5]:
                logger.info(
                    "  [%s] article=%s source=%s label=%s",
                    r["extraction_method"],
                    r["article_id"],
                    r["source_name"],
                    r["sentiment_label"],
                )
            if len(bq_rows) > 5:
                logger.info("  ... and %d more", len(bq_rows) - 5)
            return len(bq_rows)

        inserted = _batch_insert(bq_rows, config.bigquery.sentiment_table)
        logger.info("Sentiment backfill: %d inserted", inserted)
        return inserted
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entity backfill
# ---------------------------------------------------------------------------


def backfill_entity_events(
    dry_run: bool = False, since: Optional[datetime] = None
) -> int:
    logger.info("\n=== Backfilling entity_events ===")
    if not config.bigquery.enable_bigquery and not dry_run:
        logger.error("BigQuery disabled.")
        return 0

    db = SessionLocal()
    try:
        query = (
            db.query(
                ArticleEntity.article_id,
                Article.url.label("article_url"),
                Article.title.label("article_title"),
                Source.name.label("source_name"),
                Article.published_at,
                ArticleEntity.analyzed_at.label("ingested_at"),
                Entity.name.label("entity_name"),
                Entity.type.label("entity_type"),
                ArticleEntity.salience,
                ArticleEntity.mention_count,
                Entity.wikipedia_url,
                Article.sentiment_label,
                Article.sentiment_score,
                Article.language,
            )
            .join(Entity, ArticleEntity.entity_id == Entity.id)
            .join(Article, ArticleEntity.article_id == Article.id)
            .join(Source, Article.source_id == Source.id)
        )
        if since:
            query = query.filter(ArticleEntity.analyzed_at >= since)

        rows = query.order_by(ArticleEntity.analyzed_at.asc()).all()
        logger.info("Found %d entity-article links in PostgreSQL", len(rows))
        if not rows:
            return 0

        existing_ids = (
            set() if dry_run else _get_existing_event_ids(config.bigquery.entity_table)
        )
        if existing_ids:
            logger.info("Found %d existing event IDs in BigQuery", len(existing_ids))

        bq_rows: List[Dict[str, Any]] = []
        skipped = 0

        for row in rows:
            event_id = f"{row.article_id}_ent_{row.entity_name[:20]}_{int(row.ingested_at.timestamp())}"
            if event_id in existing_ids:
                skipped += 1
                continue

            bq_rows.append(
                {
                    "event_id": event_id,
                    "article_id": row.article_id,
                    "article_url": row.article_url,
                    "article_title": row.article_title,
                    "source_name": row.source_name,
                    "published_at": row.published_at.isoformat()
                    if row.published_at
                    else None,
                    "ingested_at": row.ingested_at.isoformat()
                    if row.ingested_at
                    else None,
                    "entity_name": row.entity_name,
                    "entity_type": row.entity_type,
                    "salience": row.salience,
                    "mention_count": row.mention_count,
                    "wikipedia_url": row.wikipedia_url,
                    "sentiment_label": row.sentiment_label,
                    "sentiment_score": row.sentiment_score,
                    "language": row.language,
                }
            )

        logger.info("Skipped: %d | To insert: %d", skipped, len(bq_rows))

        if dry_run:
            for r in bq_rows[:5]:
                logger.info(
                    "  %s (%s) article=%s salience=%.2f",
                    r["entity_name"],
                    r["entity_type"],
                    r["article_id"],
                    r["salience"] or 0,
                )
            if len(bq_rows) > 5:
                logger.info("  ... and %d more", len(bq_rows) - 5)
            return len(bq_rows)

        inserted = _batch_insert(bq_rows, config.bigquery.entity_table)
        logger.info("Entity backfill: %d inserted", inserted)
        return inserted
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Category backfill
# ---------------------------------------------------------------------------


def backfill_category_events(
    dry_run: bool = False, since: Optional[datetime] = None
) -> int:
    logger.info("\n=== Backfilling category_events ===")
    if not config.bigquery.enable_bigquery and not dry_run:
        logger.error("BigQuery disabled.")
        return 0

    db = SessionLocal()
    try:
        query = (
            db.query(
                ArticleCategory.article_id,
                Source.name.label("source_name"),
                Article.published_at,
                ArticleCategory.analyzed_at.label("ingested_at"),
                ArticleCategory.name.label("category_name"),
                ArticleCategory.confidence.label("category_confidence"),
                Article.sentiment_label,
                Article.sentiment_score,
                Article.language,
            )
            .join(Article, ArticleCategory.article_id == Article.id)
            .join(Source, Article.source_id == Source.id)
        )
        if since:
            query = query.filter(ArticleCategory.analyzed_at >= since)

        rows = query.order_by(ArticleCategory.analyzed_at.asc()).all()
        logger.info("Found %d article-category links in PostgreSQL", len(rows))
        if not rows:
            return 0

        existing_ids = (
            set()
            if dry_run
            else _get_existing_event_ids(config.bigquery.category_table)
        )
        if existing_ids:
            logger.info("Found %d existing event IDs in BigQuery", len(existing_ids))

        bq_rows: List[Dict[str, Any]] = []
        skipped = 0

        for row in rows:
            event_id = f"{row.article_id}_cat_{row.category_name[:30]}_{int(row.ingested_at.timestamp())}"
            if event_id in existing_ids:
                skipped += 1
                continue

            bq_rows.append(
                {
                    "event_id": event_id,
                    "article_id": row.article_id,
                    "source_name": row.source_name,
                    "published_at": row.published_at.isoformat()
                    if row.published_at
                    else None,
                    "ingested_at": row.ingested_at.isoformat()
                    if row.ingested_at
                    else None,
                    "category_name": row.category_name,
                    "category_confidence": row.category_confidence,
                    "sentiment_label": row.sentiment_label,
                    "sentiment_score": row.sentiment_score,
                    "language": row.language,
                }
            )

        logger.info("Skipped: %d | To insert: %d", skipped, len(bq_rows))

        if dry_run:
            for r in bq_rows[:5]:
                logger.info(
                    "  %s confidence=%.2f article=%s",
                    r["category_name"],
                    r["category_confidence"] or 0,
                    r["article_id"],
                )
            if len(bq_rows) > 5:
                logger.info("  ... and %d more", len(bq_rows) - 5)
            return len(bq_rows)

        inserted = _batch_insert(bq_rows, config.bigquery.category_table)
        logger.info("Category backfill: %d inserted", inserted)
        return inserted
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sentiment_only = "--sentiment-only" in sys.argv

    since = None
    for arg in sys.argv:
        if arg.startswith("--since="):
            since = datetime.fromisoformat(arg.split("=", 1)[1]).replace(
                tzinfo=timezone.utc
            )

    if dry_run:
        logger.info("DRY RUN mode\n")

    s = backfill_sentiment_events(dry_run=dry_run, since=since)

    if not sentiment_only:
        e = backfill_entity_events(dry_run=dry_run, since=since)
        c = backfill_category_events(dry_run=dry_run, since=since)
    else:
        e, c = 0, 0
        logger.info("\nSkipping entity/category (--sentiment-only)")

    logger.info("\n=== Summary ===")
    logger.info("Sentiment: %d | Entities: %d | Categories: %d", s, e, c)
