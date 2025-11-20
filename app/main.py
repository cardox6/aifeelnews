from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models.article  # noqa: F401
import app.models.article_content  # noqa: F401
import app.models.bookmark  # noqa: F401
import app.models.crawl_job  # noqa: F401
import app.models.sentiment_analysis  # noqa: F401
import app.models.source  # noqa: F401
import app.models.user  # noqa: F401
from app.database import Base, engine  # noqa: F401
from app.routers import articles, bookmarks, sources, users

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
        from app.jobs.run_ingestion import run_ingestion

        # Run ingestion in background (non-blocking for scheduler)
        run_ingestion(include_crawling=True, max_crawl_jobs=3)

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
