from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models to register them with SQLAlchemy
from app import models  # noqa: F401
from app.database import Base, engine  # noqa: F401
from app.routers import articles, bookmarks, sentiment, sources, users

app = FastAPI(title="aiFeelNews API")

# Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(articles.router, prefix="/articles", tags=["Articles"])
app.include_router(bookmarks.router, prefix="/bookmarks", tags=["Bookmarks"])
app.include_router(sources.router, prefix="/sources", tags=["Sources"])
app.include_router(sentiment.router)


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


@app.get("/ready")
def readiness_check() -> dict[str, str]:
    """Readiness check for Kubernetes deployments."""
    return {"status": "ready", "service": "aifeelnews-api"}


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
