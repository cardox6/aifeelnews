import logging
import sys

from app.database import SessionLocal
from app.jobs.crawl_worker import run_crawl_worker
from app.jobs.fetch_from_mediastack import fetch_all_sources
from app.jobs.ingest_articles import ingest_articles
from app.jobs.normalize_articles import normalize_articles

logging.basicConfig(level=logging.INFO, format="%(message)s")
# silence all INFO‐level SQL logs:
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def run_ingestion(include_crawling: bool = True, max_crawl_jobs: int = 5) -> None:
    """
    Run the complete ingestion pipeline.

    Args:
        include_crawling: Whether to run crawl worker after ingestion
        max_crawl_jobs: Maximum crawl jobs to process if crawling enabled
    """
    logging.info("\n🚀 Starting ingestion pipeline…")

    # Step 1: Fetch articles from Mediastack
    logging.info("📡 Fetching articles from Mediastack...")
    raw = fetch_all_sources()

    # Step 2: Normalize article data
    logging.info("🔄 Normalizing article data...")
    norm = normalize_articles(raw)

    # Step 3: Ingest articles into database
    logging.info("💾 Ingesting articles into database...")
    db = SessionLocal()
    try:
        new = ingest_articles(db, norm)
        logging.info("✅ Ingested %d new articles", new)
    finally:
        db.close()

    # Step 4: Run crawl worker (if enabled)
    if include_crawling:
        logging.info("\n🕷️ Running crawl worker for content extraction...")
        crawl_result = run_crawl_worker(max_jobs=max_crawl_jobs)

        logging.info("🏁 Crawl worker completed:")
        logging.info("   Jobs processed: %d", crawl_result["processed"])
        logging.info("   Successful: %d", crawl_result["successful"])
        logging.info("   Failed: %d", crawl_result["failed"])
        logging.info("   New jobs created: %d", crawl_result["new_jobs_created"])
        logging.info("   Duration: %.2f seconds", crawl_result["duration"])

        if crawl_result["successful"] > 0:
            logging.info(
                "✅ Successfully extracted content from %d articles",
                crawl_result["successful"],
            )

        if crawl_result["failed"] > 0:
            logging.info(
                "⚠️ %d crawl jobs failed (may be rate-limited for retry)",
                crawl_result["failed"],
            )

    logging.info("\n🎉 Ingestion pipeline completed!")


if __name__ == "__main__":
    # Parse command line arguments
    include_crawling = True
    max_crawl_jobs = 5

    if len(sys.argv) > 1:
        if sys.argv[1] == "--no-crawl":
            include_crawling = False
        elif sys.argv[1] == "--crawl-only":
            # Skip ingestion, just run crawl worker
            logging.info("🕷️ Running crawl worker only...")
            result = run_crawl_worker(max_jobs=max_crawl_jobs)
            logging.info(
                "✅ Crawl worker completed: %d successful, %d failed",
                result["successful"],
                result["failed"],
            )
            sys.exit(0)
        elif sys.argv[1].startswith("--max-crawl="):
            max_crawl_jobs = int(sys.argv[1].split("=")[1])

    run_ingestion(include_crawling=include_crawling, max_crawl_jobs=max_crawl_jobs)
