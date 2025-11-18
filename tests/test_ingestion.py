"""Test basic ingestion functionality."""

from app.jobs.ingest_articles import get_or_create_source, ingest_articles
from app.jobs.normalize_articles import normalize_articles
from app.models.article import Article


def test_get_or_create_source(test_db):
    """Test source creation and retrieval."""
    # Test creating a new source
    source1 = get_or_create_source(test_db, "test-source")
    assert source1.name == "test-source"
    assert source1.id is not None

    # Test retrieving existing source
    source2 = get_or_create_source(test_db, "test-source")
    assert source1.id == source2.id


def test_normalize_articles():
    """Test article normalization logic."""
    raw_articles = [
        {
            "title": "Test Article",
            "description": "Test description",
            "url": "https://example.com/article?utm=test#fragment",
            "published_at": "2025-11-18T10:00:00Z",
            "source_name": "test-source",
            "language": "en",
            "country": "us",
            "category": "general",
        }
    ]

    normalized = normalize_articles(raw_articles)

    assert len(normalized) == 1
    article = normalized[0]

    # Check URL canonicalization (query and fragment removed)
    assert article["url"] == "https://example.com/article"
    assert article["sentiment_label"] in ["positive", "negative", "neutral"]
    assert isinstance(article["sentiment_score"], float)


def test_ingest_articles(test_db):
    """Test article ingestion with deduplication."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    articles = [
        {
            "title": "Test Article 1",
            "description": "Description 1",
            "url": "https://example.com/article1",
            "image_url": None,
            "published_at": now,
            "language": "en",
            "country": "us",
            "category": "general",
            "sentiment_label": "neutral",
            "sentiment_score": 0.0,
            "source_name": "test-source",
        },
        {
            "title": "Test Article 2",
            "description": "Description 2",
            "url": "https://example.com/article1",  # Duplicate URL
            "image_url": None,
            "published_at": now,
            "language": "en",
            "country": "us",
            "category": "general",
            "sentiment_label": "neutral",
            "sentiment_score": 0.0,
            "source_name": "test-source",
        },
    ]

    # First ingestion should add 1 article
    added = ingest_articles(test_db, articles)
    assert added == 1

    # Second ingestion should add 0 (duplicate URL)
    added = ingest_articles(test_db, articles)
    assert added == 0

    # Verify only 1 article exists in DB
    count = test_db.query(Article).count()
    assert count == 1
