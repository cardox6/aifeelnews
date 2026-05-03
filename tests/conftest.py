"""Test configuration and fixtures."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 — register all ORM models on Base.metadata
from app.database import Base


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh in-memory SQLite database for each test.

    StaticPool keeps a single connection alive for every request, including
    those FastAPI's TestClient runs in its threadpool — without it, each new
    connection opens a separate ``:memory:`` database with no tables.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables - fresh in-memory database so no conflicts
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()
