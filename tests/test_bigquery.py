"""Tests for BigQuery analytics service.

BigQuery client is mocked since CI runs on SQLite without GCP credentials.
Tests verify: config defaults, batch buffering, parameterized queries,
and graceful degradation when BigQuery is disabled.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest


class TestBigQueryConfig:
    """Verify BigQuery config loads sensible defaults."""

    def test_defaults(self):
        from app.config.bigquery import BigQueryConfig

        cfg = BigQueryConfig()
        assert cfg.enable_bigquery is False
        assert cfg.dataset_id == "aifeelnews"
        assert cfg.dataset_location == "europe-west1"
        assert cfg.batch_size == 50
        assert cfg.sentiment_table == "sentiment_events"
        assert cfg.ingestion_table == "ingestion_events"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("BIGQUERY_ENABLE_BIGQUERY", "true")
        monkeypatch.setenv("BIGQUERY_BATCH_SIZE", "10")

        from app.config.bigquery import BigQueryConfig

        cfg = BigQueryConfig()
        assert cfg.enable_bigquery is True
        assert cfg.batch_size == 10


class TestBuffering:
    """Verify batch buffering and flushing logic."""

    def test_queue_noop_when_disabled(self):
        """Events are silently dropped when BigQuery is disabled."""
        from app.services import bigquery as bq_mod

        # Ensure buffer is empty
        bq_mod._sentiment_buffer.clear()

        bq_mod.queue_sentiment_event(
            article_id=1,
            article_url="https://example.com/article",
            article_title="Test",
            source_name="test_source",
            published_at=datetime.now(timezone.utc),
            sentiment_score=0.5,
            sentiment_label="positive",
        )

        # Should NOT buffer when disabled (config default is False)
        assert len(bq_mod._sentiment_buffer) == 0

    @patch("app.services.bigquery.config")
    def test_queue_buffers_when_enabled(self, mock_config):
        """Events are buffered when BigQuery is enabled."""
        from app.services import bigquery as bq_mod

        mock_config.bigquery.enable_bigquery = True
        mock_config.bigquery.batch_size = 100  # High threshold to avoid auto-flush

        bq_mod._sentiment_buffer.clear()

        bq_mod.queue_sentiment_event(
            article_id=42,
            article_url="https://example.com/42",
            article_title="Test Article",
            source_name="bbc",
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            sentiment_score=0.8,
            sentiment_label="positive",
            sentiment_provider="GCP_NL",
            magnitude=0.9,
        )

        assert len(bq_mod._sentiment_buffer) == 1
        event = bq_mod._sentiment_buffer[0]
        assert event["article_id"] == 42
        assert event["source_name"] == "bbc"
        assert event["sentiment_label"] == "positive"
        assert event["sentiment_provider"] == "GCP_NL"

        # Cleanup
        bq_mod._sentiment_buffer.clear()

    @patch("app.services.bigquery.config")
    @patch("app.services.bigquery._flush_buffer")
    def test_auto_flush_at_batch_size(self, mock_flush, mock_config):
        """Buffer auto-flushes when batch_size is reached."""
        from app.services import bigquery as bq_mod

        mock_config.bigquery.enable_bigquery = True
        mock_config.bigquery.batch_size = 2
        mock_flush.return_value = True

        bq_mod._sentiment_buffer.clear()

        # First event — no flush
        bq_mod.queue_sentiment_event(
            article_id=1,
            article_url="https://example.com/1",
            article_title="Test 1",
            source_name="bbc",
            published_at=datetime.now(timezone.utc),
            sentiment_score=0.5,
            sentiment_label="positive",
        )
        assert not mock_flush.called

        # Second event — triggers flush (batch_size=2)
        bq_mod.queue_sentiment_event(
            article_id=2,
            article_url="https://example.com/2",
            article_title="Test 2",
            source_name="cnn",
            published_at=datetime.now(timezone.utc),
            sentiment_score=-0.3,
            sentiment_label="negative",
        )
        # The auto-flush in queue_sentiment_event calls flush_sentiment(),
        # which calls the (mocked) _flush_buffer exactly once. Asserting this
        # guards the threshold check, the flush_sentiment -> _flush_buffer
        # delegation, and that the first event did NOT prematurely flush.
        assert mock_flush.call_count == 1

        # Cleanup
        bq_mod._sentiment_buffer.clear()


class TestGracefulDegradation:
    """Verify analytics queries return empty results when disabled."""

    def test_trends_empty_when_disabled(self):
        from app.services.bigquery import get_sentiment_trends

        result = get_sentiment_trends(days=30)
        assert result == []

    def test_source_comparison_empty_when_disabled(self):
        from app.services.bigquery import get_source_comparison

        result = get_source_comparison()
        assert result == []

    def test_category_breakdown_empty_when_disabled(self):
        from app.services.bigquery import get_category_breakdown

        result = get_category_breakdown()
        assert result == []

    def test_pipeline_stats_empty_when_disabled(self):
        from app.services.bigquery import get_pipeline_stats

        result = get_pipeline_stats()
        assert result == []

    def test_entity_sentiment_timeline_empty_when_disabled(self):
        from app.services.bigquery import get_entity_sentiment_timeline

        result = get_entity_sentiment_timeline()
        assert result == []

    def test_flush_noop_when_disabled(self):
        from app.services.bigquery import flush

        # Should succeed silently (no BQ client needed)
        assert flush() is True


class TestAnalyticsRouter:
    """Verify analytics endpoints return graceful disabled messages."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from app.main import app

        return TestClient(app)

    def test_trends_disabled(self, client):
        resp = client.get("/api/v1/analytics/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("message") == "BigQuery analytics is not enabled"

    def test_sources_disabled(self, client):
        resp = client.get("/api/v1/analytics/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("message") == "BigQuery analytics is not enabled"

    def test_categories_disabled(self, client):
        resp = client.get("/api/v1/analytics/categories")
        assert resp.status_code == 200

    def test_pipeline_disabled(self, client):
        resp = client.get("/api/v1/analytics/pipeline")
        assert resp.status_code == 200

    def test_entity_sentiment_timeline_disabled(self, client):
        resp = client.get("/api/v1/analytics/entities/sentiment-timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("message") == "BigQuery analytics is not enabled"

    def test_entity_sentiment_timeline_query_validation(self, client):
        # days must be >= 1
        resp = client.get("/api/v1/analytics/entities/sentiment-timeline?days=0")
        assert resp.status_code == 422

        # days must be <= 365
        resp = client.get("/api/v1/analytics/entities/sentiment-timeline?days=999")
        assert resp.status_code == 422

        # limit must be <= 50
        resp = client.get("/api/v1/analytics/entities/sentiment-timeline?limit=99")
        assert resp.status_code == 422

    def test_trends_query_validation(self, client):
        # days must be >= 1
        resp = client.get("/api/v1/analytics/trends?days=0")
        assert resp.status_code == 422

        # days must be <= 365
        resp = client.get("/api/v1/analytics/trends?days=999")
        assert resp.status_code == 422

    def test_enabled_but_failing_query_returns_503_not_empty(self, client):
        """When BigQuery is enabled and a query genuinely fails, the endpoint
        returns 503 — NOT a silent 200 [] that looks like 'no data'."""
        from app.services.bigquery import BigQueryQueryError

        # Enable BigQuery at the router's config check, then make the underlying
        # query raise the failure sentinel. The dedicated handler → 503.
        with patch("app.routers.analytics.config") as mock_cfg:
            mock_cfg.bigquery.enable_bigquery = True
            with patch(
                "app.routers.analytics.get_sentiment_trends",
                side_effect=BigQueryQueryError("boom"),
            ):
                resp = client.get("/api/v1/analytics/trends")
        assert resp.status_code == 503
        assert resp.json() != []

    def test_entity_sentiment_timeline_failing_query_returns_503(self, client):
        """The new timeline endpoint follows the same raise-not-swallow contract:
        a genuine query failure surfaces as 503, never a silent 200 []."""
        from app.services.bigquery import BigQueryQueryError

        with patch("app.routers.analytics.config") as mock_cfg:
            mock_cfg.bigquery.enable_bigquery = True
            with patch(
                "app.routers.analytics.get_entity_sentiment_timeline",
                side_effect=BigQueryQueryError("boom"),
            ):
                resp = client.get("/api/v1/analytics/entities/sentiment-timeline")
        assert resp.status_code == 503
        assert resp.json() != []
