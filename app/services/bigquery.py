"""
BigQuery analytics service for aiFeelNews.

Provides batch-buffered streaming of sentiment/ingestion events and
parameterized analytics queries for dashboard endpoints.

All queries use @param + QueryJobConfig — no f-string SQL.
Table/dataset identifiers come from validated Pydantic config,
never from user input.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import config

logger = logging.getLogger(__name__)


class BigQueryQueryError(Exception):
    """A BigQuery analytics query failed at runtime (auth/quota/schema drift).

    Raised instead of swallowing the error and returning [] so the API can
    distinguish 'the query failed' (→ 503) from 'there are legitimately no
    rows' (→ 200 []). Caught by a dedicated handler in app/main.py.
    """


# ---------------------------------------------------------------------------
# Lazy client initialisation
# ---------------------------------------------------------------------------
_client: Any = None
_tables_provisioned: bool = False


def _get_client() -> Any:
    """Return a BigQuery client, creating one on first call."""
    global _client
    if _client is not None:
        return _client

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    cfg = config.bigquery
    _client = bigquery.Client(
        project=cfg.project_id,  # None → auto-detect from environment
        location=cfg.dataset_location,
    )
    return _client


def _ensure_tables() -> None:
    """One-time provisioning — create dataset + tables if they don't exist."""
    global _tables_provisioned
    if _tables_provisioned:
        return

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]
    from google.cloud.exceptions import (
        NotFound,  # type: ignore[import-untyped,attr-defined]
    )

    client = _get_client()
    cfg = config.bigquery

    # --- Dataset ---
    dataset_ref = client.dataset(cfg.dataset_id)
    try:
        client.get_dataset(dataset_ref)
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = cfg.dataset_location
        client.create_dataset(dataset)
        logger.info("Created BigQuery dataset %s", cfg.dataset_id)

    # --- sentiment_events ---
    _ensure_table(
        client,
        cfg.dataset_id,
        cfg.sentiment_table,
        _sentiment_schema(),
        partition_field="ingested_at",
        clustering_fields=["sentiment_label", "source_name"],
    )

    # --- ingestion_events ---
    _ensure_table(
        client,
        cfg.dataset_id,
        cfg.ingestion_table,
        _ingestion_schema(),
        partition_field="started_at",
    )

    # --- entity_events ---
    _ensure_table(
        client,
        cfg.dataset_id,
        cfg.entity_table,
        _entity_schema(),
        partition_field="ingested_at",
        clustering_fields=["entity_type", "entity_name"],
    )

    # --- category_events ---
    _ensure_table(
        client,
        cfg.dataset_id,
        cfg.category_table,
        _category_schema(),
        partition_field="ingested_at",
        clustering_fields=["category_name"],
    )

    _tables_provisioned = True
    logger.info("BigQuery tables provisioned")


def _ensure_table(
    client: Any,
    dataset_id: str,
    table_id: str,
    schema: list,
    partition_field: str,
    clustering_fields: Optional[list] = None,
) -> None:
    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]
    from google.cloud.exceptions import (
        NotFound,  # type: ignore[import-untyped,attr-defined]
    )

    table_ref = client.dataset(dataset_id).table(table_id)
    try:
        client.get_table(table_ref)
    except NotFound:
        table = bigquery.Table(table_ref, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_field,
        )
        if clustering_fields:
            table.clustering_fields = clustering_fields
        client.create_table(table)
        logger.info("Created BigQuery table %s.%s", dataset_id, table_id)


# ---------------------------------------------------------------------------
# Table schemas
# ---------------------------------------------------------------------------


def _sentiment_schema() -> list:
    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    return [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("article_id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("article_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("article_title", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("source_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("sentiment_provider", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_model", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_score", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_magnitude", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_label", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("confidence", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("language", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("category", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("content_length", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("processing_time_ms", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("extraction_method", "STRING", mode="NULLABLE"),
    ]


def _ingestion_schema() -> list:
    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    return [
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("finished_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("duration_seconds", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("articles_fetched", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("articles_ingested", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("crawl_successful", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("crawl_failed", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("include_crawling", "BOOLEAN", mode="REQUIRED"),
    ]


def _entity_schema() -> list:
    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    return [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("article_id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("article_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("article_title", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("source_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("entity_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("entity_type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("salience", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("mention_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("wikipedia_url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_label", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_score", "FLOAT", mode="NULLABLE"),
    ]


def _category_schema() -> list:
    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    return [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("article_id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("source_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("published_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("category_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("category_confidence", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_label", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("sentiment_score", "FLOAT", mode="NULLABLE"),
    ]


# ---------------------------------------------------------------------------
# Batch-buffered streaming
# ---------------------------------------------------------------------------
_sentiment_buffer: List[Dict[str, Any]] = []
_ingestion_buffer: List[Dict[str, Any]] = []
_entity_buffer: List[Dict[str, Any]] = []
_category_buffer: List[Dict[str, Any]] = []


def queue_sentiment_event(
    article_id: int,
    article_url: str,
    article_title: str,
    source_name: str,
    published_at: datetime,
    sentiment_score: float,
    sentiment_label: str,
    sentiment_provider: str = "VADER",
    **kwargs: Any,
) -> None:
    """Buffer a sentiment event; auto-flushes at batch_size."""
    if not config.bigquery.enable_bigquery:
        return

    now_utc = datetime.now(timezone.utc)
    _sentiment_buffer.append(
        {
            "event_id": f"{article_id}_{sentiment_provider}_{int(now_utc.timestamp())}",
            "article_id": article_id,
            "article_url": article_url,
            "article_title": article_title,
            "source_name": source_name,
            "published_at": published_at.isoformat(),
            "ingested_at": now_utc.isoformat(),
            "sentiment_provider": sentiment_provider,
            "sentiment_model": kwargs.get("model_name", ""),
            "sentiment_score": sentiment_score,
            "sentiment_magnitude": kwargs.get("magnitude"),
            "sentiment_label": sentiment_label,
            "confidence": kwargs.get("confidence"),
            "language": kwargs.get("language", "en"),
            "country": kwargs.get("country"),
            "category": kwargs.get("category"),
            "content_length": kwargs.get("content_length"),
            "processing_time_ms": kwargs.get("processing_time_ms"),
            "extraction_method": kwargs.get("extraction_method", "web_crawl"),
        }
    )

    if len(_sentiment_buffer) >= config.bigquery.batch_size:
        flush_sentiment()


def queue_ingestion_event(
    started_at: datetime,
    finished_at: datetime,
    duration_seconds: float,
    articles_fetched: int,
    articles_ingested: int,
    include_crawling: bool,
    crawl_successful: Optional[int] = None,
    crawl_failed: Optional[int] = None,
) -> None:
    """Buffer an ingestion pipeline run event."""
    if not config.bigquery.enable_bigquery:
        return

    _ingestion_buffer.append(
        {
            "run_id": str(uuid.uuid4()),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": duration_seconds,
            "articles_fetched": articles_fetched,
            "articles_ingested": articles_ingested,
            "crawl_successful": crawl_successful,
            "crawl_failed": crawl_failed,
            "include_crawling": include_crawling,
        }
    )

    if len(_ingestion_buffer) >= config.bigquery.batch_size:
        flush_ingestion()


def queue_entity_event(
    article_id: int,
    article_url: str,
    article_title: str,
    source_name: str,
    published_at: datetime,
    entity_name: str,
    entity_type: str,
    salience: float,
    mention_count: int,
    sentiment_label: str,
    sentiment_score: float,
    wikipedia_url: Optional[str] = None,
) -> None:
    """Buffer an entity event; auto-flushes at batch_size."""
    if not config.bigquery.enable_bigquery:
        return

    now_utc = datetime.now(timezone.utc)
    _entity_buffer.append(
        {
            "event_id": f"{article_id}_ent_{entity_name[:20]}_{int(now_utc.timestamp())}",
            "article_id": article_id,
            "article_url": article_url,
            "article_title": article_title,
            "source_name": source_name,
            "published_at": published_at.isoformat() if published_at else None,
            "ingested_at": now_utc.isoformat(),
            "entity_name": entity_name,
            "entity_type": entity_type,
            "salience": salience,
            "mention_count": mention_count,
            "wikipedia_url": wikipedia_url,
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
        }
    )

    if len(_entity_buffer) >= config.bigquery.batch_size:
        flush_entities()


def queue_category_event(
    article_id: int,
    source_name: str,
    published_at: datetime,
    category_name: str,
    category_confidence: float,
    sentiment_label: str,
    sentiment_score: float,
) -> None:
    """Buffer a category event; auto-flushes at batch_size."""
    if not config.bigquery.enable_bigquery:
        return

    now_utc = datetime.now(timezone.utc)
    _category_buffer.append(
        {
            "event_id": f"{article_id}_cat_{category_name[:30]}_{int(now_utc.timestamp())}",
            "article_id": article_id,
            "source_name": source_name,
            "published_at": published_at.isoformat() if published_at else None,
            "ingested_at": now_utc.isoformat(),
            "category_name": category_name,
            "category_confidence": category_confidence,
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
        }
    )

    if len(_category_buffer) >= config.bigquery.batch_size:
        flush_categories()


def flush_sentiment() -> bool:
    """Flush sentiment buffer to BigQuery. Returns True on success."""
    return _flush_buffer(
        _sentiment_buffer,
        config.bigquery.sentiment_table,
    )


def flush_ingestion() -> bool:
    """Flush ingestion buffer to BigQuery. Returns True on success."""
    return _flush_buffer(
        _ingestion_buffer,
        config.bigquery.ingestion_table,
    )


def flush_entities() -> bool:
    """Flush entity buffer to BigQuery. Returns True on success."""
    return _flush_buffer(
        _entity_buffer,
        config.bigquery.entity_table,
    )


def flush_categories() -> bool:
    """Flush category buffer to BigQuery. Returns True on success."""
    return _flush_buffer(
        _category_buffer,
        config.bigquery.category_table,
    )


def flush() -> bool:
    """Flush all buffers. Call at end of pipeline runs."""
    s = flush_sentiment()
    i = flush_ingestion()
    e = flush_entities()
    c = flush_categories()
    return s and i and e and c


def _flush_buffer(buffer: List[Dict[str, Any]], table_id: str) -> bool:
    if not buffer:
        return True
    if not config.bigquery.enable_bigquery:
        buffer.clear()
        return True

    try:
        _ensure_tables()
        client = _get_client()
        cfg = config.bigquery
        table_ref = client.dataset(cfg.dataset_id).table(table_id)
        table = client.get_table(table_ref)

        errors = client.insert_rows_json(table, list(buffer))
        if errors:
            # Not in an except block — no exception object to attach.
            logger.error("BigQuery insert errors for %s: %s", table_id, errors)
            return False

        logger.info(
            "Flushed %d rows to BigQuery %s.%s",
            len(buffer),
            cfg.dataset_id,
            table_id,
        )
        buffer.clear()
        return True

    except Exception as e:
        logger.error("BigQuery flush failed for %s: %s", table_id, e, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Parameterized analytics queries
# ---------------------------------------------------------------------------


def _table_fqn(table_id: str) -> str:
    """Fully-qualified table name from config (safe — not user input)."""
    cfg = config.bigquery
    project = cfg.project_id or _get_client().project
    return f"`{project}.{cfg.dataset_id}.{table_id}`"


def get_sentiment_trends(
    days: int = 30,
    source_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Sentiment trends over time, optionally filtered by source."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.sentiment_table)

    query = f"""
    SELECT
        DATE(ingested_at) AS date,
        sentiment_label,
        COUNT(*) AS article_count,
        AVG(sentiment_score) AS avg_sentiment_score,
        AVG(sentiment_magnitude) AS avg_magnitude
    FROM {fqn}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND (@source IS NULL OR source_name = @source)
    GROUP BY date, sentiment_label
    ORDER BY date DESC, sentiment_label
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
            bigquery.ScalarQueryParameter("source", "STRING", source_name),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Sentiment trends query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Sentiment trends query failed") from e


def get_source_comparison(days: int = 30) -> List[Dict[str, Any]]:
    """Sentiment comparison across news sources."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.sentiment_table)

    query = f"""
    SELECT
        source_name,
        sentiment_label,
        COUNT(*) AS article_count,
        AVG(sentiment_score) AS avg_sentiment_score,
        ROUND(
            COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY source_name),
            2
        ) AS percentage
    FROM {fqn}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND source_name IS NOT NULL
    GROUP BY source_name, sentiment_label
    ORDER BY source_name, sentiment_label
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Source comparison query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Source comparison query failed") from e


def get_category_breakdown(days: int = 30) -> List[Dict[str, Any]]:
    """Sentiment breakdown by article category."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.sentiment_table)

    query = f"""
    SELECT
        category,
        COUNT(*) AS article_count,
        AVG(sentiment_score) AS avg_sentiment_score,
        AVG(sentiment_magnitude) AS avg_magnitude
    FROM {fqn}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND category IS NOT NULL
    GROUP BY category
    ORDER BY article_count DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Category breakdown query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Category breakdown query failed") from e


def get_pipeline_stats(days: int = 7) -> List[Dict[str, Any]]:
    """Ingestion pipeline run statistics."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.ingestion_table)

    query = f"""
    SELECT
        run_id,
        started_at,
        finished_at,
        duration_seconds,
        articles_fetched,
        articles_ingested,
        crawl_successful,
        crawl_failed,
        include_crawling
    FROM {fqn}
    WHERE started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
    ORDER BY started_at DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Pipeline stats query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Pipeline stats query failed") from e


# ---------------------------------------------------------------------------
# Entity & category analytics queries
# ---------------------------------------------------------------------------


def get_top_entities(
    days: int = 30,
    entity_type: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Top entities by article mention count."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.entity_table)

    query = f"""
    SELECT
        entity_name,
        entity_type,
        COUNT(DISTINCT article_id) AS article_count,
        AVG(salience) AS avg_salience,
        AVG(sentiment_score) AS avg_sentiment_score
    FROM {fqn}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND (@entity_type IS NULL OR entity_type = @entity_type)
      AND entity_type NOT IN ('NUMBER', 'OTHER', 'DATE', 'PRICE', 'ADDRESS', 'PHONE_NUMBER')
    GROUP BY entity_name, entity_type
    ORDER BY article_count DESC
    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
            bigquery.ScalarQueryParameter("entity_type", "STRING", entity_type),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Top entities query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Top entities query failed") from e


def get_entity_sentiment(
    days: int = 30,
    entity_type: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Per-entity sentiment statistics."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.entity_table)

    query = f"""
    SELECT
        entity_name,
        entity_type,
        COUNT(DISTINCT article_id) AS article_count,
        AVG(sentiment_score) AS avg_sentiment_score,
        AVG(salience) AS avg_salience
    FROM {fqn}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND (@entity_type IS NULL OR entity_type = @entity_type)
    GROUP BY entity_name, entity_type
    HAVING COUNT(DISTINCT article_id) >= 2
    ORDER BY avg_sentiment_score DESC
    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
            bigquery.ScalarQueryParameter("entity_type", "STRING", entity_type),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Entity sentiment query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Entity sentiment query failed") from e


def get_entity_sentiment_timeline(
    days: int = 30,
    entity_type: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Per-day average sentiment for the top-N most-mentioned entities."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.entity_table)

    query = f"""
    WITH top_entities AS (
        SELECT entity_name, entity_type
        FROM {fqn}
        WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
          AND (@entity_type IS NULL OR entity_type = @entity_type)
          AND entity_type NOT IN ('NUMBER', 'OTHER', 'DATE', 'PRICE', 'ADDRESS', 'PHONE_NUMBER')
        GROUP BY entity_name, entity_type
        ORDER BY COUNT(DISTINCT article_id) DESC
        LIMIT @limit
    )
    SELECT
        DATE(e.ingested_at) AS date,
        e.entity_name,
        e.entity_type,
        COUNT(DISTINCT e.article_id) AS article_count,
        AVG(e.sentiment_score) AS avg_sentiment_score
    FROM {fqn} AS e
    JOIN top_entities AS t
      ON e.entity_name = t.entity_name AND e.entity_type = t.entity_type
    WHERE e.ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND (@entity_type IS NULL OR e.entity_type = @entity_type)
      AND e.entity_type NOT IN ('NUMBER', 'OTHER', 'DATE', 'PRICE', 'ADDRESS', 'PHONE_NUMBER')
    GROUP BY date, e.entity_name, e.entity_type
    ORDER BY date ASC, article_count DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
            bigquery.ScalarQueryParameter("entity_type", "STRING", entity_type),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("Entity sentiment timeline query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("Entity sentiment timeline query failed") from e


def get_nlp_categories(
    days: int = 30,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """GCP NL content categories with sentiment aggregation."""
    if not config.bigquery.enable_bigquery:
        return []

    from google.cloud import bigquery  # type: ignore[import-untyped,attr-defined]

    fqn = _table_fqn(config.bigquery.category_table)

    query = f"""
    SELECT
        category_name,
        COUNT(DISTINCT article_id) AS article_count,
        AVG(category_confidence) AS avg_confidence,
        AVG(sentiment_score) AS avg_sentiment_score
    FROM {fqn}
    WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
      AND category_name IS NOT NULL
    GROUP BY category_name
    ORDER BY article_count DESC
    LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("days", "INT64", days),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ]
    )

    try:
        results = _get_client().query(query, job_config=job_config)
        return [dict(row) for row in results]
    except Exception as e:
        logger.error("NLP categories query failed: %s", e, exc_info=True)
        raise BigQueryQueryError("NLP categories query failed") from e
