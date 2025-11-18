"""Tests for new database models and functionality."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.jobs.ttl_cleanup import cleanup_expired_content, get_content_statistics
from app.models.article import Article
from app.models.article_content import ArticleContent
from app.models.crawl_job import CrawlJob, CrawlStatus
from app.models.sentiment_analysis import SentimentAnalysis
from app.models.source import Source


def test_crawl_job_model(test_db):
    """Test CrawlJob model functionality."""
    # Create source and article first
    source = Source(name="test-source")
    test_db.add(source)
    test_db.flush()

    now = datetime.now(timezone.utc)
    article = Article(
        source_id=source.id,
        title="Test Article",
        url="https://example.com/test",
        published_at=now,
    )
    test_db.add(article)
    test_db.flush()

    # Create crawl job
    crawl_job = CrawlJob(
        article_id=article.id, status=CrawlStatus.PENDING, robots_allowed=True
    )
    test_db.add(crawl_job)
    test_db.commit()

    # Test relationships
    assert crawl_job.article == article
    assert article.crawl_jobs[0] == crawl_job

    # Test status enum
    assert crawl_job.status == CrawlStatus.PENDING

    # Update status
    crawl_job.status = CrawlStatus.SUCCESS
    crawl_job.http_status = 200
    crawl_job.bytes_downloaded = 1500
    test_db.commit()

    # Verify updates
    retrieved = test_db.query(CrawlJob).filter_by(article_id=article.id).first()
    assert retrieved.status == CrawlStatus.SUCCESS
    assert retrieved.http_status == 200
    assert retrieved.bytes_downloaded == 1500


def test_article_content_model(test_db):
    """Test ArticleContent model and TTL functionality."""
    # Create source and article first
    source = Source(name="test-source")
    test_db.add(source)
    test_db.flush()

    now = datetime.now(timezone.utc)
    article = Article(
        source_id=source.id,
        title="Test Article",
        url="https://example.com/test",
        published_at=now,
    )
    test_db.add(article)
    test_db.flush()

    # Create article content with TTL
    expires_at = now + timedelta(hours=24)
    content = ArticleContent(
        article_id=article.id,
        content_text="This is a truncated article content...",  # Max 1024 chars
        content_hash="abc123def456",
        content_length=5000,  # Original length before truncation
        expires_at=expires_at,
    )
    test_db.add(content)
    test_db.commit()

    # Test relationships
    assert content.article == article
    assert article.content == content

    # Test unique constraint (one content per article)
    duplicate_content = ArticleContent(
        article_id=article.id,
        content_text="Different content",
        content_hash="different_hash",
        content_length=3000,
        expires_at=expires_at,
    )
    test_db.add(duplicate_content)

    with pytest.raises(IntegrityError):
        test_db.commit()


def test_sentiment_analysis_model(test_db):
    """Test SentimentAnalysis model functionality."""
    # Create source and article first
    source = Source(name="test-source")
    test_db.add(source)
    test_db.flush()

    now = datetime.now(timezone.utc)
    article = Article(
        source_id=source.id,
        title="Test Article",
        url="https://example.com/test",
        published_at=now,
    )
    test_db.add(article)
    test_db.flush()

    # Create multiple sentiment analyses (different providers)
    vader_analysis = SentimentAnalysis(
        article_id=article.id,
        provider="VADER",
        model_name="vader_lexicon",
        score=0.75,
        label="positive",
        language="en",
    )

    gcp_analysis = SentimentAnalysis(
        article_id=article.id,
        provider="GCP_NL",
        model_name="gcp_nl_v1",
        score=0.65,
        magnitude=0.8,
        label="positive",
        language="en",
    )

    test_db.add(vader_analysis)
    test_db.add(gcp_analysis)
    test_db.commit()

    # Test relationships
    assert len(article.sentiment_analyses) == 2
    assert vader_analysis.article == article
    assert gcp_analysis.article == article

    # Test querying by provider
    vader_result = (
        test_db.query(SentimentAnalysis)
        .filter_by(article_id=article.id, provider="VADER")
        .first()
    )
    assert vader_result.score == 0.75
    assert vader_result.magnitude is None  # VADER doesn't have magnitude

    gcp_result = (
        test_db.query(SentimentAnalysis)
        .filter_by(article_id=article.id, provider="GCP_NL")
        .first()
    )
    assert gcp_result.magnitude == 0.8


def test_ttl_cleanup_functionality(test_db):
    """Test TTL cleanup job functionality."""
    # Create source and articles
    source = Source(name="test-source")
    test_db.add(source)
    test_db.flush()

    now = datetime.now(timezone.utc)

    # Article 1 with expired content
    article1 = Article(
        source_id=source.id,
        title="Article 1",
        url="https://example.com/article1",
        published_at=now,
    )
    test_db.add(article1)
    test_db.flush()

    expired_content = ArticleContent(
        article_id=article1.id,
        content_text="Expired content",
        content_hash="expired_hash",
        content_length=1000,
        expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
    )
    test_db.add(expired_content)

    # Article 2 with active content
    article2 = Article(
        source_id=source.id,
        title="Article 2",
        url="https://example.com/article2",
        published_at=now,
    )
    test_db.add(article2)
    test_db.flush()

    active_content = ArticleContent(
        article_id=article2.id,
        content_text="Active content",
        content_hash="active_hash",
        content_length=1500,
        expires_at=now + timedelta(hours=23),  # Expires in 23 hours
    )
    test_db.add(active_content)
    test_db.commit()

    # Verify initial state
    total_content = test_db.query(ArticleContent).count()
    assert total_content == 2

    # Get statistics before cleanup
    stats_before = get_content_statistics(test_db)
    assert stats_before["total_records"] == 2
    assert stats_before["expired_records"] == 1
    assert stats_before["active_records"] == 1

    # Run TTL cleanup
    result = cleanup_expired_content(test_db)
    assert result["status"] == "success"
    assert result["deleted_count"] == 1

    # Verify cleanup worked
    remaining_content = test_db.query(ArticleContent).count()
    assert remaining_content == 1

    # The active content should still be there
    remaining = test_db.query(ArticleContent).first()
    assert remaining.content_hash == "active_hash"

    # Get statistics after cleanup
    stats_after = get_content_statistics(test_db)
    assert stats_after["total_records"] == 1
    assert stats_after["expired_records"] == 0
    assert stats_after["active_records"] == 1


def test_cascade_deletions(test_db):
    """Test that cascade deletions work properly."""
    # Create source and article
    source = Source(name="test-source")
    test_db.add(source)
    test_db.flush()

    now = datetime.now(timezone.utc)
    article = Article(
        source_id=source.id,
        title="Test Article",
        url="https://example.com/test",
        published_at=now,
    )
    test_db.add(article)
    test_db.flush()

    # Create related records
    crawl_job = CrawlJob(article_id=article.id, status=CrawlStatus.SUCCESS)

    content = ArticleContent(
        article_id=article.id,
        content_text="Test content",
        content_hash="test_hash",
        content_length=1000,
        expires_at=now + timedelta(hours=24),
    )

    sentiment = SentimentAnalysis(
        article_id=article.id, provider="VADER", score=0.5, label="neutral"
    )

    test_db.add(crawl_job)
    test_db.add(content)
    test_db.add(sentiment)
    test_db.commit()

    # Verify all records exist
    assert test_db.query(CrawlJob).count() == 1
    assert test_db.query(ArticleContent).count() == 1
    assert test_db.query(SentimentAnalysis).count() == 1

    # Delete the article - should cascade to all related records
    test_db.delete(article)
    test_db.commit()

    # Verify cascade deletion worked
    assert test_db.query(Article).count() == 0
    assert test_db.query(CrawlJob).count() == 0
    assert test_db.query(ArticleContent).count() == 0
    assert test_db.query(SentimentAnalysis).count() == 0
