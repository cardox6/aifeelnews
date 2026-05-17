import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import models  # noqa: F401
from app.config import config as _app_config
from app.database import Base, engine  # noqa: F401
from app.deps.oidc import verify_scheduler_oidc
from app.routers import articles, bookmarks, sources, users
from app.utils.logging import setup_logging

# Structured logging (JSON in production, plain text locally)
setup_logging()
logger = logging.getLogger(__name__)

logger.info(
    "aiFeelNews starting [env=%s, mediastack_key=%s]",
    os.getenv("ENV", "local"),
    "SET" if _app_config.ingestion.mediastack_api_key else "EMPTY",
)

# Import sentiment router with error handling
sentiment_available = False
sentiment: Any = None
try:
    from app.routers import sentiment

    sentiment_available = True
except Exception as e:
    logger.warning("Could not import sentiment router: %s", e, exc_info=True)
    sentiment_available = False

# Import entities router with error handling
entities_available = False
entities_mod: Any = None
try:
    from app.routers import entities as entities_mod

    entities_available = True
except Exception as e:
    logger.warning("Could not import entities router: %s", e, exc_info=True)
    entities_available = False

# Import analytics router with error handling
analytics_available = False
analytics_mod: Any = None
try:
    from app.routers import analytics as analytics_mod

    analytics_available = True
except Exception as e:
    logger.warning("Could not import analytics router: %s", e, exc_info=True)
    analytics_available = False

APP_VERSION = os.getenv("APP_VERSION", "1.0.1")
app = FastAPI(title="aiFeelNews API", version=APP_VERSION)

# --- Rate limiting (slowapi) -------------------------------------------------
# `get_remote_address` keys requests by client IP. Cloud Run forwards the real
# client IP via X-Forwarded-For; slowapi reads the request object's `client.host`
# which Starlette populates from that header when running behind a proxy.
# We register the limiter on app.state so route decorators can find it via
# `request.app.state.limiter` and add a handler that translates the
# RateLimitExceeded exception into a clean 429 response.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
# slowapi's handler signature is `(Request, RateLimitExceeded) -> Response`
# whereas Starlette's `add_exception_handler` expects the second arg to be
# typed as `Exception`. The function itself works at runtime (RateLimitExceeded
# IS-A Exception); we cast away the false-positive type mismatch here.
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,  # type: ignore[arg-type]
)

# Allowed origins for CORS (production Firebase Hosting + local dev)
ALLOWED_ORIGINS = [
    "https://aifeelnews-front.web.app",
    "https://aifeelnews-front.firebaseapp.com",
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

# Register entities router if available
if entities_available and entities_mod:
    app.include_router(entities_mod.router, prefix="/api/v1/entities")

# Register analytics router if available
if analytics_available and analytics_mod:
    app.include_router(analytics_mod.router, prefix="/api/v1/analytics")

# Register PostgreSQL analytics router (advanced SQL: window functions, CTEs, GROUPING SETS)
db_analytics_available = False
db_analytics_mod: Any = None
try:
    from app.routers import db_analytics as db_analytics_mod

    db_analytics_available = True
except Exception as e:
    logger.warning("Could not import db_analytics router: %s", e, exc_info=True)

if db_analytics_available and db_analytics_mod:
    app.include_router(db_analytics_mod.router, prefix="/api/v1/db-analytics")


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

        logger.error("Service unavailable at health DB check: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
        )


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
    """Readiness probe — verifies DB connectivity before accepting traffic."""
    try:
        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()

        return {"status": "ready", "service": "aifeelnews-api"}
    except Exception as e:
        from fastapi import HTTPException

        logger.error("Service unavailable at readiness DB check: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
        )


@app.get("/metrics", tags=["Meta"])
def metrics() -> dict[str, Any]:
    """Lightweight application metrics for observability dashboards."""
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models.article import Article
    from app.models.crawl_job import CrawlJob
    from app.models.sentiment_analysis import SentimentAnalysis
    from app.models.source import Source

    db = SessionLocal()
    try:
        # SQLAlchemy 2.0 select() style — proper type support
        article_count = db.execute(select(func.count(Article.id))).scalar() or 0
        source_count = db.execute(select(func.count(Source.id))).scalar() or 0
        crawl_total = db.execute(select(func.count(CrawlJob.id))).scalar() or 0
        sentiment_total = (
            db.execute(select(func.count(SentimentAnalysis.id))).scalar() or 0
        )

        # Access column via __table__.c to avoid mypy conflict with
        # legacy Column() type annotations on the model class
        status_col = CrawlJob.__table__.c.status
        crawl_by_status = {
            str(row.status): row.count
            for row in db.execute(
                select(status_col, func.count(CrawlJob.id).label("count")).group_by(
                    status_col
                )
            )
        }

        sentiment_by_label = {
            str(row.label): row.count
            for row in db.execute(
                select(
                    SentimentAnalysis.label,
                    func.count(SentimentAnalysis.id).label("count"),
                ).group_by(SentimentAnalysis.label)
            )
        }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "articles": {"total": article_count, "sources": source_count},
            "crawl_jobs": {"total": crawl_total, "by_status": crawl_by_status},
            "sentiment": {"analyzed": sentiment_total, "by_label": sentiment_by_label},
            "database": {"status": "connected"},
        }
    except Exception as e:
        # Log the full exception server-side; return only a generic
        # marker to the client so internal detail (DB errors, paths)
        # is not exposed (CodeQL py/stack-trace-exposure).
        logger.error("Metrics collection failed: %s", e, exc_info=True)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": "metrics collection failed",
        }
    finally:
        db.close()


@app.post("/api/v1/trigger-ingestion")
@limiter.limit(_app_config.security.rate_limit_scheduler)
def trigger_ingestion(
    request: Request,
    _claims: dict[str, str] = Depends(verify_scheduler_oidc),
) -> dict[str, str]:
    """Trigger news ingestion pipeline - used by Cloud Scheduler.

    Protected by Cloud Scheduler OIDC verification (see
    ``app/deps/oidc.py``) so only Scheduler running as ``cloudrun-sa``
    can hit this. Rate limited to 6/hour by default to defend against
    accidental loops; Scheduler's own cadence is every 8 hours.
    """
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

        logger.error("Service unavailable at trigger-ingestion: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
        )


@app.post("/api/v1/cleanup")
@limiter.limit(_app_config.security.rate_limit_scheduler)
def trigger_cleanup(
    request: Request,
    _claims: dict[str, str] = Depends(verify_scheduler_oidc),
) -> dict[str, Any]:
    """Trigger database cleanup - used by Cloud Scheduler for maintenance.

    Protected by Cloud Scheduler OIDC verification (see
    ``app/deps/oidc.py``). Rate limited to 6/hour as a defence-in-depth
    measure; Scheduler runs cleanup once per day.
    """
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

        logger.error("Service unavailable at cleanup: %s", e, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
        )
