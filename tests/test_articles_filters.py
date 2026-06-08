"""Tests for the filter / search / pagination contract on /api/v1/articles routes.

These exercise the shared ``_query_articles`` helper through the public
``/api/v1/articles/`` endpoint via TestClient. ``/api/v1/articles/latest``
reuses the same helper so a single smoke test covers it.

The tests run against the in-memory SQLite ``test_db`` fixture from
``tests/conftest.py``. Auth is irrelevant here because the article list
routes are unauthenticated.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.article import Article
from app.models.source import Source


@pytest.fixture
def seeded_db(test_db: Session) -> Iterator[Session]:
    """Seed the in-memory DB with two sources and ten varied articles.

    Distribution:
      - sentiment_label: 4 positive, 3 negative, 3 neutral
      - category: 4 general, 3 business, 3 sports
      - source_id: 5 from source 1, 5 from source 2
      - one title contains "trump" so the substring search test has a hit
    """
    source1 = Source(id=1, name="bbc")
    source2 = Source(id=2, name="cnn")
    test_db.add_all([source1, source2])
    test_db.flush()

    base_time = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)

    # (title, sentiment_label, category, source_id)
    rows: list[tuple[str, str, str, int]] = [
        ("Markets rally after Trump speech", "positive", "business", 1),
        ("Olympic team announces new roster", "positive", "sports", 2),
        ("Scientists discover quantum advance", "positive", "general", 1),
        ("Local festival draws record crowd", "positive", "general", 2),
        ("Layoffs hit major tech firm", "negative", "business", 1),
        ("Storm causes widespread damage", "negative", "general", 2),
        ("Team loses championship final", "negative", "sports", 1),
        ("Central bank holds rates steady", "neutral", "business", 2),
        ("New stadium opens to public", "neutral", "sports", 1),
        ("City council debates new policy", "neutral", "general", 2),
    ]

    for idx, (title, sentiment, category, source_id) in enumerate(rows):
        test_db.add(
            Article(
                source_id=source_id,
                title=title,
                url=f"https://example.com/articles/{idx}",
                published_at=base_time - timedelta(hours=idx),
                sentiment_label=sentiment,
                category=category,
            )
        )
    test_db.commit()

    yield test_db


@pytest.fixture
def client(seeded_db: Session) -> Iterator[TestClient]:
    """A TestClient with ``get_db`` overridden to yield the seeded session."""

    def _override_get_db() -> Iterator[Session]:
        yield seeded_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestArticleFilters:
    """Filter / search / pagination + 422 boundary cases on /api/v1/articles/."""

    def test_articles_default(self, client: TestClient) -> None:
        """No params: default page returns all 10 seeded rows."""
        resp = client.get("/api/v1/articles/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10
        # Stable order: newest first by published_at.
        published = [a["published_at"] for a in data]
        assert published == sorted(published, reverse=True)

    def test_articles_filter_by_sentiment(self, client: TestClient) -> None:
        """sentiment_label=positive returns exactly the 4 positive rows."""
        resp = client.get("/api/v1/articles/?sentiment_label=positive")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        assert all(a["sentiment_label"] == "positive" for a in data)

    def test_articles_filter_by_category(self, client: TestClient) -> None:
        """category=business returns exactly the 3 business rows."""
        resp = client.get("/api/v1/articles/?category=business")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert all(a["category"] == "business" for a in data)

    def test_articles_filter_by_source(self, client: TestClient) -> None:
        """source_id=1 returns exactly the 5 rows from source 1."""
        resp = client.get("/api/v1/articles/?source_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        assert all(a["source"]["id"] == 1 for a in data)

    def test_articles_search_substring(self, client: TestClient) -> None:
        """Case-insensitive substring search on title; matches "trump"."""
        resp = client.get("/api/v1/articles/?search=trump")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "Trump" in data[0]["title"]

    def test_articles_pagination(self, client: TestClient) -> None:
        """skip+limit yield disjoint id sets across consecutive pages."""
        page1 = client.get("/api/v1/articles/?skip=0&limit=5").json()
        page2 = client.get("/api/v1/articles/?skip=5&limit=5").json()

        assert len(page1) == 5
        assert len(page2) == 5

        ids1 = {a["id"] for a in page1}
        ids2 = {a["id"] for a in page2}
        assert ids1.isdisjoint(ids2)
        assert len(ids1 | ids2) == 10

    def test_articles_filter_combination(self, client: TestClient) -> None:
        """Filters AND together: positive + business = 1 row (Trump speech)."""
        resp = client.get(
            "/api/v1/articles/?sentiment_label=positive&category=business"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sentiment_label"] == "positive"
        assert data[0]["category"] == "business"

    def test_articles_invalid_sentiment_returns_422(self, client: TestClient) -> None:
        """Values outside the regex enum (positive|negative|neutral) → 422."""
        resp = client.get("/api/v1/articles/?sentiment_label=ecstatic")
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_articles_invalid_skip_returns_422(self, client: TestClient) -> None:
        """skip < 0 violates the ge=0 constraint → 422."""
        resp = client.get("/api/v1/articles/?skip=-1")
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_articles_search_too_short_returns_422(self, client: TestClient) -> None:
        """search shorter than min_length=2 → 422."""
        resp = client.get("/api/v1/articles/?search=a")
        assert resp.status_code == 422
        assert "detail" in resp.json()


def test_latest_accepts_same_query_params(client: TestClient) -> None:
    """Smoke test: /api/v1/articles/latest shares the helper, so the same filter
    surface must work end-to-end. We assert filter semantics, not response
    shape (already covered above)."""
    resp = client.get("/api/v1/articles/latest?sentiment_label=neutral&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert all(a["sentiment_label"] == "neutral" for a in data)


def test_bad_stored_image_url_does_not_500_the_list(
    seeded_db: Session, client: TestClient
) -> None:
    """A row with a non-HTTP(S) image_url (stored verbatim from upstream) must
    not 500 the whole list. ArticleRead coerces it to null instead of raising."""
    seeded_db.add(
        Article(
            source_id=1,
            title="Protocol-relative image article",
            url="https://example.com/articles/bad-image",
            image_url="//cdn.example.com/x.jpg",  # no http(s) scheme
            published_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
            sentiment_label="neutral",
            category="general",
        )
    )
    seeded_db.commit()

    resp = client.get("/api/v1/articles/?limit=50")
    assert resp.status_code == 200
    bad = [
        a for a in resp.json() if a["url"] == "https://example.com/articles/bad-image"
    ]
    assert len(bad) == 1
    assert bad[0]["image_url"] is None  # coerced, page still served
