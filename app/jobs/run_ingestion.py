import logging

from app.database import SessionLocal
from app.jobs.fetch_from_mediastack import fetch_all_sources
from app.jobs.ingest_articles import ingest_articles
from app.jobs.normalize_articles import normalize_articles

logging.basicConfig(level=logging.INFO, format="%(message)s")
# silence all INFO‐level SQL logs:
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def run_ingestion() -> None:
    logging.info("\n🚀 Starting ingestion pipeline…")
    raw = fetch_all_sources()
    norm = normalize_articles(raw)
    db = SessionLocal()
    try:
        new = ingest_articles(db, norm)
        logging.info("✅ Ingested %d new articles", new)
    finally:
        db.close()


if __name__ == "__main__":
    run_ingestion()
