"""
BigQuery integration for aiFeelNews analytics.

This module provides a simple interface to stream sentiment data
to BigQuery for advanced analytics and reporting.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from app.config import settings

logger = logging.getLogger(__name__)


class BigQuerySentimentRepository:
    """Repository for streaming sentiment analysis data to BigQuery."""

    def __init__(self):
        """Initialize BigQuery client."""
        self.client = bigquery.Client() if settings.ENABLE_BIGQUERY else None
        self.dataset_id = "aifeelnews"
        self.table_id = "sentiment_events"

    def ensure_dataset_exists(self) -> None:
        """Create dataset if it doesn't exist."""
        if not self.client:
            return

        dataset_ref = self.client.dataset(self.dataset_id)

        try:
            self.client.get_dataset(dataset_ref)
            logger.info(f"Dataset {self.dataset_id} already exists")
        except NotFound:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"  # or your preferred location
            dataset = self.client.create_dataset(dataset)
            logger.info(f"Created dataset {self.dataset_id}")

    def ensure_table_exists(self) -> None:
        """Create sentiment events table if it doesn't exist."""
        if not self.client:
            return

        table_ref = self.client.dataset(self.dataset_id).table(self.table_id)

        try:
            self.client.get_table(table_ref)
            logger.info(f"Table {self.table_id} already exists")
        except NotFound:
            schema = [
                bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("article_id", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("article_url", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("article_title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("source_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("published_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
                # Sentiment analysis fields
                bigquery.SchemaField("sentiment_provider", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("sentiment_model", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("sentiment_score", "FLOAT", mode="REQUIRED"),
                bigquery.SchemaField("sentiment_magnitude", "FLOAT", mode="NULLABLE"),
                bigquery.SchemaField("sentiment_label", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("confidence", "FLOAT", mode="NULLABLE"),
                # Article metadata
                bigquery.SchemaField("language", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("category", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("content_length", "INTEGER", mode="NULLABLE"),
                # Processing metadata
                bigquery.SchemaField("processing_time_ms", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("extraction_method", "STRING", mode="NULLABLE"),
            ]

            table = bigquery.Table(table_ref, schema=schema)

            # Partition by ingested_at for better performance
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY, field="ingested_at"
            )

            # Cluster by sentiment_label and source for better query performance
            table.clustering_fields = ["sentiment_label", "source_name"]

            table = self.client.create_table(table)
            logger.info(f"Created table {self.table_id}")

    def stream_sentiment_event(self, event_data: Dict) -> bool:
        """
        Stream a sentiment analysis event to BigQuery.

        Args:
            event_data: Dictionary containing sentiment analysis data

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.info("BigQuery client not configured, skipping stream")
            return False

        try:
            self.ensure_dataset_exists()
            self.ensure_table_exists()

            table_ref = self.client.dataset(self.dataset_id).table(self.table_id)
            table = self.client.get_table(table_ref)

            # Prepare row for insertion
            rows_to_insert = [event_data]

            errors = self.client.insert_rows_json(table, rows_to_insert)

            if errors:
                logger.error(f"BigQuery insert errors: {errors}")
                return False

            logger.info(
                f"Successfully streamed sentiment event for article {event_data.get('article_id')}"
            )
            return True

        except Exception as e:
            logger.error(f"Error streaming to BigQuery: {e}")
            return False

    def get_sentiment_trends(
        self, days: int = 30, source_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Get sentiment trends over time.

        Args:
            days: Number of days to look back
            source_name: Optional source filter

        Returns:
            List of trend data points
        """
        if not self.client:
            return []

        source_filter = ""
        if source_name:
            source_filter = f"AND source_name = '{source_name}'"

        query = f"""
        SELECT
            DATE(ingested_at) as date,
            sentiment_label,
            COUNT(*) as article_count,
            AVG(sentiment_score) as avg_sentiment_score,
            AVG(sentiment_magnitude) as avg_magnitude
        FROM `{self.client.project}.{self.dataset_id}.{self.table_id}`
        WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        {source_filter}
        GROUP BY date, sentiment_label
        ORDER BY date DESC, sentiment_label
        """

        try:
            results = self.client.query(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error querying sentiment trends: {e}")
            return []

    def get_source_sentiment_comparison(self) -> List[Dict]:
        """Get sentiment comparison across news sources."""
        if not self.client:
            return []

        query = f"""
        SELECT
            source_name,
            sentiment_label,
            COUNT(*) as article_count,
            AVG(sentiment_score) as avg_sentiment_score,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(PARTITION BY source_name), 2) as percentage
        FROM `{self.client.project}.{self.dataset_id}.{self.table_id}`
        WHERE ingested_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        AND source_name IS NOT NULL
        GROUP BY source_name, sentiment_label
        ORDER BY source_name, sentiment_label
        """

        try:
            results = self.client.query(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error querying source comparison: {e}")
            return []


# Singleton instance
bigquery_repo = BigQuerySentimentRepository()


def stream_article_sentiment(
    article_id: int,
    article_url: str,
    article_title: str,
    source_name: str,
    published_at: datetime,
    sentiment_score: float,
    sentiment_label: str,
    sentiment_provider: str = "VADER",
    **kwargs,
) -> bool:
    """
    Convenience function to stream article sentiment data to BigQuery.

    Args:
        article_id: Article ID
        article_url: Article URL
        article_title: Article title
        source_name: News source name
        published_at: Article publication timestamp
        sentiment_score: Sentiment score (-1.0 to 1.0)
        sentiment_label: Sentiment label (positive/negative/neutral)
        sentiment_provider: Provider used (VADER, GCP_NL, etc.)
        **kwargs: Additional fields (magnitude, confidence, etc.)

    Returns:
        True if successful, False otherwise
    """
    event_data = {
        "event_id": f"{article_id}_{sentiment_provider}_{int(datetime.now().timestamp())}",
        "article_id": article_id,
        "article_url": article_url,
        "article_title": article_title,
        "source_name": source_name,
        "published_at": published_at.isoformat(),
        "ingested_at": datetime.utcnow().isoformat(),
        "sentiment_provider": sentiment_provider,
        "sentiment_model": kwargs.get("model_name", "vader_lexicon"),
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

    return bigquery_repo.stream_sentiment_event(event_data)
