import os
import sys
import dotenv

dotenv.load_dotenv

# Set up the project root so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from database import SessionLocal
from models import article, bookmark, user, source
from jobs.fetch_from_mediastack import fetch_articles_from_sources
from jobs.normalize_articles import normalize_articles
from jobs.ingest_articles import ingest_articles
from jobs.sources_list import SOURCES

def run_ingestion():
    print("\n🚀 Fetching raw articles...")
    raw_articles = []
    for source in SOURCES:
        print(f"🔎 Fetching from source: {source}")
        articles = fetch_articles_from_sources(source)
        raw_articles.extend(articles)

    print(f"✅ Total articles fetched: {len(raw_articles)}")

    print("\n⚙️ Normalizing articles...")
    normalized_articles = normalize_articles(raw_articles)
    print(f"✅ Total articles normalized: {len(normalized_articles)}")

    print("\n💾 Ingesting into database...")
    db: Session = SessionLocal()
    try:
        ingest_articles(db, normalized_articles)
        print("✅ Ingestion completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    run_ingestion()
