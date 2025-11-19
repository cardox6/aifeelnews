#!/usr/bin/env python3
"""
Test script for the crawl worker.

This script creates some test articles and runs the crawl worker
to validate that robots.txt compliance and content extraction work.
"""

from datetime import datetime, timezone

from app.database import SessionLocal
from app.jobs.crawl_worker import run_crawl_worker
from app.models.article import Article
from app.models.source import Source


def create_test_articles():
    """Create some test articles to crawl."""
    
    db = SessionLocal()
    
    try:
        # Check if we already have test articles
        existing_test_source = db.query(Source).filter(Source.name == "Test Source").first()
        
        if existing_test_source:
            print("✅ Test articles already exist")
            return
        
        # Create a test source
        test_source = Source(
            name="Test Source"
        )
        db.add(test_source)
        db.flush()  # Get the ID
        
        # Create test articles (mix of allowed and blocked sites)
        test_articles = [
            {
                "title": "Test BBC Article",
                "url": "https://www.bbc.com/news/technology-12345678",
                "description": "A test article from BBC (should be allowed by robots.txt)"
            },
            {
                "title": "Test TechCrunch Article", 
                "url": "https://techcrunch.com/2024/01/01/test-article/",
                "description": "A test article from TechCrunch (should be allowed by robots.txt)"
            },
            {
                "title": "Test Example Article",
                "url": "https://example.com/some-article",
                "description": "A test article from Example.com (should be blocked by robots.txt)"
            }
        ]
        
        for article_data in test_articles:
            article = Article(
                source_id=test_source.id,
                title=article_data["title"],
                description=article_data["description"],
                url=article_data["url"],
                published_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                language="en"
            )
            db.add(article)
        
        db.commit()
        print(f"✅ Created test source and {len(test_articles)} test articles")
        
    finally:
        db.close()


def main():
    """Run the crawl worker test."""
    
    print("🧪 Testing Crawl Worker")
    print("=" * 50)
    
    # Step 1: Create test articles
    print("\n📝 Creating test articles...")
    create_test_articles()
    
    # Step 2: Run the crawl worker
    print("\n🚀 Running crawl worker...")
    result = run_crawl_worker(max_jobs=5)
    
    # Step 3: Show results
    print("\n📊 Crawl Worker Test Results:")
    print("=" * 50)
    print(f"Status: {result['status']}")
    print(f"Jobs Processed: {result['processed']}")
    print(f"Successful Crawls: {result['successful']}")
    print(f"Failed Crawls: {result['failed']}")
    print(f"New Jobs Created: {result['new_jobs_created']}")
    print(f"Duration: {result['duration']:.2f} seconds")
    
    # Step 4: Check what happened
    if result['processed'] > 0:
        print(f"\n✅ Crawl worker processed {result['processed']} jobs!")
        
        if result['successful'] > 0:
            print(f"   {result['successful']} successful crawls")
        if result['failed'] > 0:
            print(f"   {result['failed']} failed crawls")
        
        print("\nNote: Check the logs above for detailed crawling results.")
        print("Robots.txt compliance should have blocked example.com URLs.")
    else:
        print("\nℹ️ No jobs were processed. This might be because:")
        print("- No articles exist in the database yet")
        print("- All articles already have crawl jobs")
        print("- All jobs are already processed")


if __name__ == "__main__":
    main()