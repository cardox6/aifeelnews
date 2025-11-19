"""Test script to demonstrate TTL functionality with sample data."""

import hashlib
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.jobs.ttl_cleanup import cleanup_expired_content, get_content_statistics
from app.models.article import Article
from app.models.article_content import ArticleContent
from app.models.source import Source
from app.utils.ttl import calculate_content_expiry, get_ttl_info


def create_sample_content():
    """Create sample content with different expiry times for testing."""
    db = SessionLocal()

    try:
        print("🔧 Creating sample content for TTL testing...")

        # Get or create a test source
        source = db.query(Source).filter_by(name="ttl-test-source").first()
        if not source:
            source = Source(name="ttl-test-source")
            db.add(source)
            db.flush()

        now = datetime.now(timezone.utc)

        # Create articles with different ages
        articles_data = [
            {
                "title": "Fresh Article (1 day old)",
                "url": "https://example.com/fresh",
                "published_at": now - timedelta(days=1),
                "content_age_days": 1,
            },
            {
                "title": "Week Old Article (7 days old)",
                "url": "https://example.com/week-old",
                "published_at": now - timedelta(days=7),
                "content_age_days": 7,
            },
            {
                "title": "Expired Article (10 days old)",
                "url": "https://example.com/expired",
                "published_at": now - timedelta(days=10),
                "content_age_days": 10,
            },
            {
                "title": "Very Fresh Article (2 hours old)",
                "url": "https://example.com/very-fresh",
                "published_at": now - timedelta(hours=2),
                "content_age_days": 0.083,  # ~2 hours in days
            },
        ]

        for article_data in articles_data:
            # Create article
            article = Article(
                source_id=source.id,
                title=article_data["title"],
                url=article_data["url"],
                published_at=article_data["published_at"],
            )
            db.add(article)
            db.flush()

            # Create content with appropriate expiry
            content_age_days = article_data["content_age_days"]
            content_extracted_at = now - timedelta(days=content_age_days)

            # Content expires 7 days after extraction
            content_expires_at = content_extracted_at + timedelta(days=7)

            content_text = f"Sample content for {article_data['title']}. This content is {content_age_days} days old."
            content_hash = hashlib.sha256(content_text.encode()).hexdigest()[:16]

            content = ArticleContent(
                article_id=article.id,
                content_text=content_text,
                content_hash=content_hash,
                content_length=len(content_text),
                extracted_at=content_extracted_at,
                expires_at=content_expires_at,
            )
            db.add(content)

            # Show what we created
            status = "EXPIRED" if content_expires_at <= now else "ACTIVE"
            print(f"  📄 {article_data['title']}")
            print(f"     Content age: {content_age_days} days")
            print(
                f"     Expires at: {content_expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            print(f"     Status: {status}")
            print()

        db.commit()
        print("✅ Sample content created successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating sample content: {e}")
        raise
    finally:
        db.close()


def test_ttl_system():
    """Run complete TTL system test."""
    print("🚀 Testing TTL System")
    print("=" * 50)

    # Show TTL configuration
    ttl_info = get_ttl_info()
    print("⚙️  TTL Configuration:")
    print(
        f"   TTL Duration: {ttl_info['ttl_hours']} hours ({ttl_info['ttl_hours']//24} days)"
    )
    print(f"   Current Time: {ttl_info['current_utc']}")
    print(f"   New Content Would Expire: {ttl_info['next_expiry_would_be']}")
    print()

    # Create sample content
    create_sample_content()

    # Show statistics before cleanup
    print("📊 Statistics BEFORE cleanup:")
    stats_before = get_content_statistics()
    print(f"   Total Records: {stats_before['total_records']}")
    print(f"   Active Records: {stats_before['active_records']}")
    print(f"   Expired Records: {stats_before['expired_records']}")
    print(f"   Average Content Length: {stats_before['average_content_length']} chars")
    print()

    # Run TTL cleanup
    print("🧹 Running TTL Cleanup...")
    cleanup_result = cleanup_expired_content()
    print(f"   Status: {cleanup_result['status']}")
    print(f"   Deleted Records: {cleanup_result['deleted_count']}")
    print(f"   Cleanup Time: {cleanup_result['cleanup_time']}")
    print()

    # Show statistics after cleanup
    print("📊 Statistics AFTER cleanup:")
    stats_after = get_content_statistics()
    print(f"   Total Records: {stats_after['total_records']}")
    print(f"   Active Records: {stats_after['active_records']}")
    print(f"   Expired Records: {stats_after['expired_records']}")
    print(f"   Average Content Length: {stats_after['average_content_length']} chars")
    print()

    # Summary
    print("📈 TTL Test Summary:")
    print(f"   Records Before: {stats_before['total_records']}")
    print(f"   Records After: {stats_after['total_records']}")
    print(f"   Records Cleaned: {cleanup_result['deleted_count']}")
    print(f"   Expired Before Cleanup: {stats_before['expired_records']}")
    print(f"   Expired After Cleanup: {stats_after['expired_records']}")

    if cleanup_result["deleted_count"] > 0:
        print("✅ TTL cleanup working correctly! Expired content was removed.")
    else:
        print("ℹ️  No expired content found to clean up.")


if __name__ == "__main__":
    test_ttl_system()
