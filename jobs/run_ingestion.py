# jobs/run_ingestion.py
import sys, os
from database import SessionLocal
from jobs.sources_list import SOURCES
from jobs.fetch_from_mediastack import fetch_articles_from_sources
from jobs.normalize_articles  import normalize_articles
from jobs.ingest_articles import ingest_articles

# allow `python -m jobs.run_ingestion`
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def run():
    print("🚀 Fetching raw articles...")
    all_raw = []
    for src in SOURCES:
        print(f"🔎 {src}")
        all_raw.extend(fetch_articles_from_sources(src))
    print(f"✅ Fetched {len(all_raw)} raw articles.")

    print("⚙️  Normalizing...")
    norm = normalize_articles(all_raw)
    print(f"✅ {len(norm)} normalized.")

    print("💾 Ingesting...")
    db = SessionLocal()
    try:
        n = ingest_articles(db, norm)
        print(f"✅ Inserted {n} new articles.")
    finally:
        db.close()

if __name__ == "__main__":
    run()
