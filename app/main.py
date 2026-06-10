import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import models  # noqa: F401
from app.config import config as _app_config
from app.database import Base, engine  # noqa: F401
from app.deps.oidc import verify_scheduler_oidc
from app.deps.ratelimit import limiter
from app.routers import (
    analytics,
    articles,
    bookmarks,
    db_analytics,
    entities,
    sentiment,
    sources,
    users,
)
from app.services.bigquery import BigQueryQueryError
from app.utils.logging import setup_logging

# Structured logging (JSON in production, plain text locally)
setup_logging()
logger = logging.getLogger(__name__)

logger.info(
    "aiFeelNews starting [env=%s, is_production=%s, mediastack_key=%s]",
    os.getenv("ENV", "local"),
    # Log the RESOLVED is_production so an ENV value that doesn't map to
    # production (and would therefore relax OIDC) is visible at boot.
    _app_config.security.is_production,
    "SET" if _app_config.ingestion.mediastack_api_key else "EMPTY",
)

APP_VERSION = os.getenv("APP_VERSION", "1.0.1")
app = FastAPI(
    title="aiFeelNews API",
    version=APP_VERSION,
    description=(
        "News sentiment-analysis API. Ingests articles (English + German), "
        "crawls original content (robots.txt-respecting), and annotates "
        "sentiment, entities, and topic categories via Google Cloud Natural "
        "Language.\n\n"
        "- **Articles / Sources / Entities** — the read API behind the SPA "
        "(search, filtering, full-text).\n"
        "- **Analytics** — BigQuery-backed trends, entity, and pipeline-health "
        "queries.\n"
        "- **DB Analytics** — real-time PostgreSQL analytics (window functions, "
        "CTEs, `GROUPING SETS`).\n"
        "- **Bookmarks** — per-user, requires a Firebase ID token.\n\n"
        "All data endpoints live under the single `/api/v1` namespace; "
        "`/health`, `/ready`, `/version`, and `/metrics` are unversioned "
        "infrastructure probes."
    ),
)

# --- Rate limiting (slowapi) -------------------------------------------------
# The shared limiter (app/deps/ratelimit.py) is registered on app.state so the
# route decorators resolve it via `request.app.state.limiter`. The handler
# translates RateLimitExceeded into a clean 429.
app.state.limiter = limiter
# slowapi's handler is typed `(Request, RateLimitExceeded)`; Starlette expects
# `Exception` for the second arg. It works at runtime (RateLimitExceeded IS-A
# Exception) — cast away the false-positive mismatch.
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,  # type: ignore[arg-type]
)


@app.exception_handler(BigQueryQueryError)
async def bigquery_query_error_handler(
    request: Request, exc: BigQueryQueryError
) -> JSONResponse:
    """A BigQuery analytics query failed at runtime → 503, not a silent 200 [].

    The analytics services raise this (instead of swallowing the error and
    returning []) so a real failure (auth/quota/schema drift) is distinguishable
    from a legitimately empty result. The frontend can then show a failure state
    rather than an empty chart that looks like "no data".
    """
    logger.error(
        "BigQuery analytics query failed on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Analytics temporarily unavailable"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler for otherwise-unhandled exceptions.

    Logs the cause server-side and returns a generic 500 so no stack trace or
    internal detail leaks to the client. HTTPException and RequestValidationError
    have their own handlers that take precedence, so domain 4xx responses and
    the per-endpoint 503s are unaffected.
    """
    logger.error(
        "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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

# Register routers. All imports are unconditional: a broken router import is a
# programming error that should fail startup loudly (caught by the deploy
# health check), not silently drop endpoints from the API.
#
# Every domain router is mounted under the single ``/api/v1`` surface so the
# API has one versioned namespace (no unprefixed legacy paths). Operational
# endpoints (/health, /ready, /version, /metrics) stay unprefixed by design —
# they're infrastructure probes, not part of the versioned data API.
# Each router declares its own ``tags=`` (see app/routers/*.py); we do NOT
# repeat the tag here or FastAPI concatenates them and Swagger shows a doubled
# label ("Articles / Articles"). Prefix only.
app.include_router(users.router, prefix="/api/v1/users")
app.include_router(articles.router, prefix="/api/v1/articles")
app.include_router(bookmarks.router, prefix="/api/v1/bookmarks")
app.include_router(sources.router, prefix="/api/v1/sources")
app.include_router(sentiment.router, prefix="/api/v1/sentiment")
app.include_router(entities.router, prefix="/api/v1/entities")
app.include_router(analytics.router, prefix="/api/v1/analytics")
# PostgreSQL analytics (advanced SQL: window functions, CTEs, GROUPING SETS)
app.include_router(db_analytics.router, prefix="/api/v1/db-analytics")


@app.get("/", tags=["Meta"])
def root() -> dict[str, str]:
    return {"message": "aiFeelNews API is running"}


@app.get("/health", tags=["Meta"])
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


@app.get("/ready", tags=["Meta"])
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
@limiter.limit(_app_config.security.rate_limit_metrics)
def metrics(request: Request) -> dict[str, Any]:
    """Lightweight application metrics for observability dashboards.

    Rate-limited (not authenticated): the deploy pipeline curls this
    unauthenticated as a hard gate and it's a public demo anchor, so the
    limiter is defence-in-depth against scraping, not access control.
    """
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


@app.post("/api/v1/trigger-ingestion", tags=["Operations"])
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


@app.post("/api/v1/cleanup", tags=["Operations"])
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
