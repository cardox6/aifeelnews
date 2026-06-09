"""Postgres-only tests for trigram-accelerated title search (migration
a3f1c2d4e5b6 + the similarity ranking in app/routers/articles.py).

These need the real pg_trgm extension and GIN index, so they are
@pytest.mark.postgres and skip when no TEST_POSTGRES_URL is set
(see conftest.pytest_collection_modifyitems). The schema — including the
trigram index — is built by the CI ``alembic upgrade head`` step before pytest
runs, so ``postgres_db`` queries hit the migrated database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.article import Article
from app.models.source import Source

pytestmark = pytest.mark.postgres


@pytest.fixture()
def seeded_pg(postgres_db: Session) -> Session:
    """Seed titles with a clear trigram-similarity gradient for "quantum".

    ``similarity(title, q)`` is the shared-trigram ratio over both strings, so a
    title where the term is a *larger fraction* scores higher. The short
    "Quantum leap…" therefore out-ranks the longer "Quantum computing…" even
    though we publish the short one OLDEST — proving the ORDER BY is relevance,
    not recency. (Verified directly against pg_trgm: 0.286 vs 0.195 vs 0.0.)
    """
    source = Source(name="testwire")
    postgres_db.add(source)
    postgres_db.flush()

    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    # (title, hours_offset) — bigger offset = older. The strongest match is the
    # oldest, so a pure published_at sort would bury it; similarity lifts it.
    rows = [
        ("Markets steady as earnings season opens", 0),  # newest, no match
        ("Quantum computing breakthrough announced", 1),  # match, longer title
        ("Quantum leap in chip design", 2),  # oldest, strongest (shorter) match
    ]
    for idx, (title, off) in enumerate(rows):
        postgres_db.add(
            Article(
                source_id=source.id,
                title=title,
                url=f"https://example.com/pg/{idx}",
                published_at=base - timedelta(hours=off),
            )
        )
    postgres_db.commit()
    return postgres_db


@pytest.fixture()
def client(seeded_pg: Session) -> TestClient:
    def _override_get_db():
        yield seeded_pg

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_title_search_uses_trigram_gin_index(seeded_pg: Session) -> None:
    """The ILIKE '%term%' search plans as a bitmap scan on the trigram GIN
    index, not a sequential scan. We force an index plan and assert the index
    name appears in the EXPLAIN output."""
    # enable_seqscan=off makes the planner prefer the index when it's eligible;
    # if the trigram index were missing this would still seq-scan (GIN is the
    # only way to satisfy a leading-wildcard ILIKE), so the assertion is real.
    seeded_pg.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        row[0]
        for row in seeded_pg.execute(
            text("EXPLAIN SELECT id FROM articles WHERE title ILIKE :pat"),
            {"pat": "%quantum%"},
        ).fetchall()
    )
    assert "ix_articles_title_trgm" in plan, plan


def test_search_ranks_by_trigram_similarity(client: TestClient) -> None:
    """On Postgres a searched query orders by trigram similarity first, so the
    strongest match leads even though it is the OLDEST row (a pure date sort
    would put it last)."""
    data = client.get("/api/v1/articles/?search=quantum").json()
    titles = [a["title"] for a in data]
    assert len(titles) == 2  # both "quantum" rows match; the markets row doesn't
    assert titles[0] == "Quantum leap in chip design"


def test_search_still_substring_filtered(client: TestClient) -> None:
    """Ranking is additive — the ILIKE substring filter still bounds the set,
    so a term present in no title returns nothing."""
    data = client.get("/api/v1/articles/?search=zzzznomatch").json()
    assert data == []
