#!/usr/bin/env python3
"""
Quick database inspection utility - shows recent articles with sentiment data
"""
import os
import sys

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.database import SessionLocal
from app.models.article import Article

def main():
    """Show recent articles with sentiment data"""
    db = SessionLocal()
    try:
        articles = db.query(Article).order_by(Article.published_at.desc()).limit(5).all()
        
        print("🔍 Recent Articles with Sentiment Analysis")
        print("=" * 60)
        
        if not articles:
            print("No articles found in database.")
            print("Run: python -m app.jobs.run_ingestion")
            return
        
        for a in articles:
            sentiment_icon = "😊" if str(a.sentiment_label) == "positive" else "😔" if str(a.sentiment_label) == "negative" else "😐"
            print(f"{sentiment_icon} {a.published_at} | {a.sentiment_label} ({a.sentiment_score})")
            print(f"   📰 {a.title}")
            print()
            
        print(f"Total articles in database: {db.query(Article).count()}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
