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


def _raw(**overrides):
    """A well-formed raw Mediastack-style record, with field overrides."""
    base = {
        "title": "A title",
        "description": "A description",
        "url": "https://example.com/ok",
        "published_at": "2025-11-18T10:00:00Z",
        "source_name": "test-source",
        "language": "en",
        "country": "us",
        "category": "general",
    }
    base.update(overrides)
    return base


def test_normalize_skips_missing_published_at():
    """A record with no published_at is dropped, not emitted with None.

    published_at is NOT NULL on the Article model; emitting None would abort
    the whole batch insert on Postgres.
    """
    raw = _raw()
    del raw["published_at"]

    assert normalize_articles([raw]) == []


def test_normalize_skips_unparseable_published_at():
    """A record with a garbage date string is dropped."""
    assert normalize_articles([_raw(published_at="not-a-date")]) == []


def test_normalize_skips_overlong_title_and_url():
    """Title/url over the column limit are dropped (truncating url would
    break the UNIQUE/dedup contract)."""
    assert normalize_articles([_raw(title="x" * 256)]) == []

    long_url = "https://example.com/" + ("a" * 1001)
    assert normalize_articles([_raw(url=long_url)]) == []


def test_normalize_truncates_short_metadata_fields():
    """Over-length language/country/category are truncated to fit the column."""
    out = normalize_articles(
        [_raw(language="english", country="usa", category="x" * 80)]
    )

    assert len(out) == 1
    assert out[0]["language"] == "en"
    assert out[0]["country"] == "us"
    assert len(out[0]["category"]) == 50


def test_ingest_isolates_a_bad_row(test_db):
    """One row that violates a DB constraint must not abort the whole batch.

    Each insert runs in its own SAVEPOINT, so a NOT NULL violation (here a
    None title that bypassed the normalizer) rolls back only that row; the
    valid rows around it still commit.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    def _article(url, title="ok"):
        return {
            "title": title,
            "description": "d",
            "url": url,
            "image_url": None,
            "published_at": now,
            "language": "en",
            "country": "us",
            "category": "general",
            "sentiment_label": "neutral",
            "sentiment_score": 0.0,
            "source_name": "test-source",
        }

    batch = [
        _article("https://example.com/good1"),
        _article("https://example.com/bad", title=None),  # NOT NULL violation
        _article("https://example.com/good2"),
    ]

    added = ingest_articles(test_db, batch)

    # The two good rows commit; the bad one is skipped — not all-or-nothing.
    assert added == 2
    urls = {a.url for a in test_db.query(Article).all()}
    assert urls == {"https://example.com/good1", "https://example.com/good2"}
