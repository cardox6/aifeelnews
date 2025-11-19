"""Simple TTL test using existing data and manual content creation."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.jobs.ttl_cleanup import cleanup_expired_content, get_content_statistics
from app.models.article import Article
from app.models.article_content import ArticleContent
from app.utils.ttl import get_ttl_info


def create_test_content_for_existing_articles():
    """Create test content for existing articles with different expiry dates."""
    db = SessionLocal()

    try:
        print("🔧 Adding TTL test content to existing articles...")

        # Get some existing articles
        articles = db.query(Article).limit(3).all()

        if not articles:
            print("❌ No articles found in database. Run ingestion first.")
            return

        now = datetime.now(timezone.utc)

        test_scenarios = [
            {
                "name": "Fresh Content (1 day old)",
                "age_days": 1,
                "should_expire": False,
            },
            {
                "name": "Borderline Content (6 days old)",
                "age_days": 6,
                "should_expire": False,
            },
            {
                "name": "Expired Content (10 days old)",
                "age_days": 10,
                "should_expire": True,
            },
        ]

        created_content = []

        for i, scenario in enumerate(test_scenarios):
            if i >= len(articles):
                break

            article = articles[i]

            # Calculate content age and expiry
            content_age_days = scenario["age_days"]
            content_extracted_at = now - timedelta(days=content_age_days)
            content_expires_at = content_extracted_at + timedelta(days=7)  # 7-day TTL

            # Create unique content text
            content_text = f"Test content for TTL demo: {scenario['name']}. Created {content_age_days} days ago. UUID: {uuid.uuid4()}"
            content_hash = hashlib.sha256(content_text.encode()).hexdigest()[:16]

            # Check if this article already has content
            existing_content = (
                db.query(ArticleContent).filter_by(article_id=article.id).first()
            )
            if existing_content:
                print(
                    f"  ⚠️ Article '{article.title[:50]}...' already has content, skipping"
                )
                continue

            # Create content
            content = ArticleContent(
                article_id=article.id,
                content_text=content_text[:1024],  # Truncate to 1024 chars
                content_hash=content_hash,
                content_length=len(content_text),
                extracted_at=content_extracted_at,
                expires_at=content_expires_at,
            )

            db.add(content)

            # Track what we created
            status = "EXPIRED" if content_expires_at <= now else "ACTIVE"
            created_content.append(
                {
                    "article_title": article.title[:50],
                    "scenario": scenario["name"],
                    "age_days": content_age_days,
                    "expires_at": content_expires_at,
                    "status": status,
                    "should_expire": scenario["should_expire"],
                }
            )

            print(f"  📄 {scenario['name']}")
            print(f"     Article: {article.title[:50]}...")
            print(f"     Content Age: {content_age_days} days")
            print(
                f"     Extracted: {content_extracted_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            print(f"     Expires: {content_expires_at.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"     Status: {status}")
            print()

        if created_content:
            db.commit()
            print(f"✅ Created {len(created_content)} test content records!")
        else:
            print("ℹ️ No new content created (articles may already have content)")

        return created_content

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating test content: {e}")
        return []
    finally:
        db.close()


def run_ttl_demo():
    """Run a complete TTL demonstration."""
    print("🚀 TTL System Demo - 7 Day Expiry")
    print("=" * 50)

    # Show current configuration
    ttl_info = get_ttl_info()
    print("⚙️ TTL Configuration:")
    print(
        f"   Duration: {ttl_info['ttl_hours']} hours ({ttl_info['ttl_hours']//24} days)"
    )
    print(
        f"   Current Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    print(f"   New Content Expires: {ttl_info['next_expiry_would_be'][:19]}Z")
    print()

    # Show initial statistics
    print("📊 Statistics BEFORE creating test content:")
    stats_initial = get_content_statistics()
    print(f"   Total Records: {stats_initial['total_records']}")
    print(f"   Active Records: {stats_initial['active_records']}")
    print(f"   Expired Records: {stats_initial['expired_records']}")
    print()

    # Create test content
    created_content = create_test_content_for_existing_articles()

    if not created_content:
        print("⚠️ No test content created, using existing content for demo")

    # Show statistics after content creation
    print("📊 Statistics AFTER creating test content:")
    stats_after_creation = get_content_statistics()
    print(f"   Total Records: {stats_after_creation['total_records']}")
    print(f"   Active Records: {stats_after_creation['active_records']}")
    print(f"   Expired Records: {stats_after_creation['expired_records']}")
    print()

    # Run TTL cleanup
    print("🧹 Running TTL Cleanup...")
    cleanup_result = cleanup_expired_content()
    print(f"   Status: {cleanup_result['status']}")
    print(f"   Deleted Records: {cleanup_result['deleted_count']}")
    print(f"   Cleanup Time: {cleanup_result['cleanup_time'][:19]}Z")
    print()

    # Show final statistics
    print("📊 Statistics AFTER TTL cleanup:")
    stats_final = get_content_statistics()
    print(f"   Total Records: {stats_final['total_records']}")
    print(f"   Active Records: {stats_final['active_records']}")
    print(f"   Expired Records: {stats_final['expired_records']}")
    print()

    # Summary
    print("📈 TTL Demo Summary:")
    print(f"   Records Before Test: {stats_initial['total_records']}")
    print(f"   Records After Creation: {stats_after_creation['total_records']}")
    print(f"   Records After Cleanup: {stats_final['total_records']}")
    print(
        f"   Content Created: {stats_after_creation['total_records'] - stats_initial['total_records']}"
    )
    print(f"   Content Cleaned: {cleanup_result['deleted_count']}")

    if cleanup_result["deleted_count"] > 0:
        print("✅ TTL cleanup working! Expired content (>7 days old) was removed.")
    else:
        print("ℹ️ No expired content found (all content is <7 days old).")

    print()
    print("🔄 Next Steps:")
    print("   • Run this daily alongside ingestion: python -m app.jobs.ttl_cleanup")
    print(
        '   • Monitor storage with: python -c "from app.jobs.ttl_cleanup import get_content_statistics; print(get_content_statistics())"'
    )


if __name__ == "__main__":
    run_ttl_demo()
