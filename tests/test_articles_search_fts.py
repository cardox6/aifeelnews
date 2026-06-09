"""Postgres-only tests for the full-text search endpoint /api/v1/articles/search
(migration b4e2d5c6f7a8 + app/crud/search.py).

These need the real generated tsvector column, the GIN index, and the
websearch_to_tsquery/ts_rank functions, so they are @pytest.mark.postgres and
skip when no TEST_POSTGRES_URL is set (see conftest.pytest_collection_modifyitems).
The schema — including search_vector — is built by the CI ``alembic upgrade head``
step before pytest runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.article import Article
from app.models.source import Source

pytestmark = pytest.mark.postgres


@pytest.fixture()
def seeded_pg(postgres_db: Session) -> Session:
    """Seed articles whose titles/descriptions exercise FTS ranking + operators.

    The generated search_vector column populates automatically on INSERT (it's
    GENERATED ALWAYS ... STORED), so no extra step is needed.
    """
    source = Source(name="testwire")
    postgres_db.add(source)
    postgres_db.flush()

    base = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    # (title, description, hours_offset)
    rows = [
        # Title hit (weight A) — should out-rank a description-only hit.
        ("Central bank raises interest rates", "Policy update from the meeting", 2),
        # Description-only hit (weight B) for "interest".
        ("Quarterly markets wrap", "Investors weigh interest and inflation", 1),
        # Phrase + boolean fixtures.
        ("Global climate summit opens", "Leaders debate climate policy targets", 3),
        ("Crypto market rally continues", "Bitcoin leads the climate of optimism", 4),
        ("Sports roundup", "No relevant tokens here", 0),
    ]
    for idx, (title, desc, off) in enumerate(rows):
        postgres_db.add(
            Article(
                source_id=source.id,
                title=title,
                description=desc,
                url=f"https://example.com/fts/{idx}",
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


def test_search_endpoint_returns_matches(client: TestClient) -> None:
    """A plain term matches both a title hit and a description hit."""
    data = client.get("/api/v1/articles/search?q=interest").json()
    titles = {a["title"] for a in data}
    assert "Central bank raises interest rates" in titles  # title (weight A)
    assert "Quarterly markets wrap" in titles  # description (weight B)
    assert "Sports roundup" not in titles


def test_title_weight_outranks_description(client: TestClient) -> None:
    """ts_rank with setweight('A') on title means a title hit ranks above a
    description-only hit for the same term."""
    data = client.get("/api/v1/articles/search?q=interest").json()
    assert data[0]["title"] == "Central bank raises interest rates"


def test_phrase_query(client: TestClient) -> None:
    """Quoted phrases are honored by websearch_to_tsquery: "climate policy"
    matches the article whose description contains that phrase, not the one
    that merely contains the word "climate" elsewhere."""
    data = client.get('/api/v1/articles/search?q="climate policy"').json()
    titles = {a["title"] for a in data}
    assert "Global climate summit opens" in titles
    assert "Crypto market rally continues" not in titles


def test_boolean_exclusion(client: TestClient) -> None:
    """Leading - excludes a term (websearch_to_tsquery grammar): climate without
    crypto drops the crypto article."""
    data = client.get("/api/v1/articles/search?q=climate -crypto").json()
    titles = {a["title"] for a in data}
    assert "Global climate summit opens" in titles
    assert "Crypto market rally continues" not in titles


def test_search_respects_date_bounds(client: TestClient) -> None:
    """The date params compose with the FTS filter."""
    # "climate" matches two rows (offsets 3 and 4 → 09:00 and 08:00). Bound to
    # >= 08:30 keeps only the 09:00 one.
    after = "2026-05-01T08:30:00Z"
    data = client.get(
        f"/api/v1/articles/search?q=climate&published_after={after}"
    ).json()
    titles = {a["title"] for a in data}
    assert titles == {"Global climate summit opens"}


def test_no_match_returns_empty(client: TestClient) -> None:
    data = client.get("/api/v1/articles/search?q=zzzznomatch").json()
    assert data == []


def test_missing_q_is_422(client: TestClient) -> None:
    """q is required."""
    assert client.get("/api/v1/articles/search").status_code == 422
