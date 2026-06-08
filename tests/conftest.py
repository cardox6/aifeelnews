"""Test configuration and fixtures."""

import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 — register all ORM models on Base.metadata
from app.database import Base

# A dedicated env var (NOT DATABASE_URL) so the Postgres fixtures never
# accidentally point at the file-SQLite the test job uses for the SQLite suite.
# CI sets this to the postgres service URL; locally it is unset, so the
# @pytest.mark.postgres tests skip and `pytest tests/` stays green with no DB.
TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")


def _postgres_available() -> bool:
    return TEST_POSTGRES_URL.startswith("postgresql")


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


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.postgres tests when no Postgres is configured.

    This is what lets `pytest tests/` pass on a machine with no Postgres: the
    view/function tests are collected but skipped, never errored.
    """
    if _postgres_available():
        return
    skip_pg = pytest.mark.skip(reason="requires Postgres (set TEST_POSTGRES_URL)")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_pg)


@pytest.fixture(scope="session")
def postgres_engine():
    """Engine bound to the migrated CI Postgres. The schema is built by the
    CI `alembic upgrade head` step before pytest runs — this fixture does NOT
    call create_all, so the views/functions/triggers actually exist."""
    if not _postgres_available():
        pytest.skip("requires Postgres (set TEST_POSTGRES_URL)")
    engine = create_engine(TEST_POSTGRES_URL, echo=False, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def postgres_db(postgres_engine):
    """Function-scoped Session on the migrated Postgres DB. Teardown truncates
    every public table so each test starts from a known state (the seed loader
    commits, so an outer-transaction rollback would not isolate)."""
    SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=postgres_engine, future=True
    )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        # Build the truncate list dynamically so it stays in sync with the
        # schema (avoids a hand-maintained list drifting from the migrations).
        tables = (
            db.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        if tables:
            joined = ", ".join(f'"{t}"' for t in tables)
            db.execute(text(f"TRUNCATE {joined} RESTART IDENTITY CASCADE"))
            db.commit()
        db.close()
