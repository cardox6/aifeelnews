import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401
from app.database import Base, engine  # noqa: F401
from app.routers import articles, bookmarks, sources, users
from app.utils.logging import setup_logging

# Structured logging (JSON in production, plain text locally)
setup_logging()
logger = logging.getLogger(__name__)

# Import sentiment router with error handling
sentiment_available = False
sentiment: Any = None
try:
    from app.routers import sentiment

    sentiment_available = True
except Exception as e:
    logger.warning(f"Could not import sentiment router: {e}")
    sentiment_available = False

APP_VERSION = os.getenv("APP_VERSION", "1.0.1")
app = FastAPI(title="aiFeelNews API", version=APP_VERSION)

# Allowed origins for CORS (production Firebase Hosting + local dev)
ALLOWED_ORIGINS = [
    "https://aifeelnews-prod.web.app",
    "https://aifeelnews-prod.firebaseapp.com",
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(articles.router, prefix="/articles", tags=["Articles"])
app.include_router(bookmarks.router, prefix="/bookmarks", tags=["Bookmarks"])
app.include_router(sources.router, prefix="/sources", tags=["Sources"])

# Register sentiment router if available
if sentiment_available and sentiment:
    app.include_router(sentiment.router, prefix="/api/v1/sentiment")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "aiFeelNews API is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint for load balancers and monitoring."""
    try:
        # Test database connection
        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()

        return {
            "status": "healthy",
            "service": "aifeelnews-api",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")


# Version endpoint for deployment verification
@app.get("/version", tags=["Meta"])
def get_version() -> dict[str, str]:
    """Return API version and build time."""
    return {
        "version": APP_VERSION,
        "build_time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    """Readiness check for Kubernetes deployments."""
    return {"status": "ready", "service": "aifeelnews-api"}


@app.get("/metrics", tags=["Meta"])
def metrics() -> dict[str, Any]:
    """Lightweight application metrics for observability dashboards."""
    from sqlalchemy import func

    from app.database import SessionLocal
    from app.models.article import Article
    from app.models.crawl_job import CrawlJob
    from app.models.sentiment_analysis import SentimentAnalysis
    from app.models.source import Source

    db = SessionLocal()
    try:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "articles": {
                "total": db.query(func.count(Article.id)).scalar() or 0,
                "sources": db.query(func.count(Source.id)).scalar() or 0,
            },
            "crawl_jobs": {
                "total": db.query(func.count(CrawlJob.id)).scalar() or 0,
                "by_status": {
                    str(status): count
                    for status, count in db.query(
                        CrawlJob.status, func.count(CrawlJob.id)
                    )
                    .group_by(CrawlJob.status)
                    .all()
                },
            },
            "sentiment": {
                "analyzed": db.query(func.count(SentimentAnalysis.id)).scalar() or 0,
                "by_label": {
                    str(label): count
                    for label, count in db.query(
                        SentimentAnalysis.sentiment_label,
                        func.count(SentimentAnalysis.id),
                    )
                    .group_by(SentimentAnalysis.sentiment_label)
                    .all()
                },
            },
            "database": {
                "status": "connected",
                "pool_size": getattr(
                    getattr(db.bind, "pool", None), "size", lambda: None
                )(),
            },
        }
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
    finally:
        db.close()


@app.post("/api/v1/trigger-ingestion")
def trigger_ingestion() -> dict[str, str]:
    """Trigger news ingestion pipeline - used by Cloud Scheduler."""
    try:
        from app.config import config
        from app.jobs.run_ingestion import run_ingestion

        # Use scheduler config for optimal crawl job sizing
        max_crawl_jobs = config.scheduler.max_crawl_jobs

        # Run ingestion with optimized parameters
        # (batch_size controlled by IngestionConfig)
        run_ingestion(include_crawling=True, max_crawl_jobs=max_crawl_jobs)

        return {
            "status": "success",
            "message": "Ingestion pipeline triggered successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=500, detail=f"Ingestion pipeline failed: {str(e)}"
        )


@app.post("/api/v1/cleanup")
def trigger_cleanup() -> dict[str, Any]:
    """Trigger database cleanup - used by Cloud Scheduler for maintenance."""
    try:
        from app.database import SessionLocal
        from app.utils.cleanup import full_database_cleanup

        # Perform comprehensive cleanup
        db = SessionLocal()
        try:
            cleanup_results = full_database_cleanup(db)

            return {
                "status": "success",
                "message": "Database cleanup completed successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": cleanup_results,
            }
        finally:
            db.close()

    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=500, detail=f"Database cleanup failed: {str(e)}"
        )
