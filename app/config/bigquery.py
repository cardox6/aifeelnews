"""
BigQuery analytics configuration.

Controls BigQuery integration for streaming sentiment/ingestion events
and serving analytics dashboard queries.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class BigQueryConfig(BaseSettings):
    """Configuration for BigQuery analytics warehouse."""

    enable_bigquery: bool = Field(
        default=False,
        description="Enable BigQuery streaming and analytics queries",
    )

    project_id: Optional[str] = Field(
        default=None,
        description="GCP project ID (auto-detected from environment if not set)",
    )

    dataset_id: str = Field(
        default="aifeelnews",
        description="BigQuery dataset ID",
    )

    dataset_location: str = Field(
        default="europe-west1",
        description="BigQuery dataset location (must match project region)",
    )

    batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of rows to buffer before flushing to BigQuery",
    )

    sentiment_table: str = Field(
        default="sentiment_events",
        description="Table name for per-article sentiment events",
    )

    ingestion_table: str = Field(
        default="ingestion_events",
        description="Table name for pipeline run metrics",
    )

    class Config:
        env_prefix = "BIGQUERY_"
        case_sensitive = False
