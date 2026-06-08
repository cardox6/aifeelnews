"""HTTP-layer tests for the /api/v1/db-analytics router.

The advanced-SQL CRUD functions are exercised against real Postgres in
test_db_analytics.py (Postgres-gated, skipped in default CI). This file covers
the ROUTER itself — query-bound validation (422), route wiring, get_db
override, and response serialization — without Postgres, by mocking the CRUD
layer. So the rate-limit decorator, the Query(ge/le) bounds, and the router
include all have regression coverage on the default SQLite CI path.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture
def client(test_db) -> Iterator[TestClient]:
    """TestClient with get_db overridden to the in-memory SQLite session.

    The CRUD functions are mocked per-test, so the session is only needed to
    satisfy the Depends(get_db) wiring; no Postgres-only SQL actually runs.
    """

    def _override_get_db() -> Iterator[object]:
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


_BASE = "/api/v1/db-analytics"

# (path, crud function name patched in app.routers.db_analytics, a valid query)
_ROUTES = [
    ("/sentiment/rolling", "sentiment_rolling_average", "days=30&window=7"),
    ("/sources/ranked", "source_sentiment_ranked", "days=30"),
    ("/sentiment/breakdown", "sentiment_grouping_sets", "days=30"),
    ("/entities/momentum", "entity_momentum", "days=14"),
    ("/categories/daily", "daily_category_sentiment_pivot", "days=14"),
]


@pytest.mark.parametrize("path,crud_name,query", _ROUTES)
def test_route_wires_to_crud_and_serializes(
    client: TestClient, path: str, crud_name: str, query: str
) -> None:
    """Each route dispatches to its CRUD function and serializes the result."""
    sentinel = [{"k": "v", "n": 1}]
    with patch(f"app.routers.db_analytics.{crud_name}", return_value=sentinel):
        resp = client.get(f"{_BASE}{path}?{query}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == sentinel


# Each tuple: (path, an out-of-bounds query that must 422)
_BOUNDARY_CASES = [
    ("/sentiment/rolling", "days=6"),  # days ge=7
    ("/sentiment/rolling", "days=366"),  # days le=365
    ("/sentiment/rolling", "days=30&window=2"),  # window ge=3
    ("/sentiment/rolling", "days=30&window=31"),  # window le=30
    ("/sources/ranked", "days=0"),  # days ge=1
    ("/entities/momentum", "days=3"),  # days ge=4
    ("/entities/momentum", "days=61"),  # days le=60
    ("/categories/daily", "days=91"),  # days le=90
]


@pytest.mark.parametrize("path,query", _BOUNDARY_CASES)
def test_query_bounds_rejected_with_422(
    client: TestClient, path: str, query: str
) -> None:
    """Out-of-range query params are rejected by FastAPI before the handler
    runs (so no DB/CRUD is touched)."""
    resp = client.get(f"{_BASE}{path}?{query}")
    assert resp.status_code == 422
