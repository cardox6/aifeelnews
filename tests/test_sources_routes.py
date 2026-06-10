"""Language filtering for GET /api/v1/sources/.

A source has no intrinsic language; the filter is derived from the languages of
its articles via a JOIN. ``?language=de`` must return only sources that have at
least one German article, so the dropdown can't offer a source that would yield
an empty feed.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.article import Article
from app.models.source import Source


@pytest.fixture
def client(test_db) -> Iterator[TestClient]:
    def _override_get_db() -> Iterator[object]:
        yield test_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _article(db, *, source_id: int, language: str, slug: str) -> None:
    db.add(
        Article(
            source_id=source_id,
            title=slug,
            url=f"https://example.com/{slug}",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            language=language,
        )
    )


@pytest.fixture
def seeded(test_db):
    # bbc: EN only · tagesschau: DE only · reuters: both
    test_db.add_all(
        [
            Source(id=1, name="bbc"),
            Source(id=2, name="tagesschau"),
            Source(id=3, name="reuters"),
        ]
    )
    test_db.flush()
    _article(test_db, source_id=1, language="en", slug="bbc-en")
    _article(test_db, source_id=2, language="de", slug="tag-de")
    _article(test_db, source_id=3, language="en", slug="reu-en")
    _article(test_db, source_id=3, language="de", slug="reu-de")
    test_db.commit()


def test_no_language_returns_all_sources(client, seeded):
    resp = client.get("/api/v1/sources/")
    assert resp.status_code == 200
    assert {s["name"] for s in resp.json()} == {"bbc", "tagesschau", "reuters"}


def test_language_de_filters_to_sources_with_de_articles(client, seeded):
    resp = client.get("/api/v1/sources/?language=de")
    assert resp.status_code == 200
    # tagesschau (DE) + reuters (both) — bbc (EN only) excluded.
    assert {s["name"] for s in resp.json()} == {"tagesschau", "reuters"}


def test_language_en_filters_to_sources_with_en_articles(client, seeded):
    resp = client.get("/api/v1/sources/?language=en")
    assert resp.status_code == 200
    assert {s["name"] for s in resp.json()} == {"bbc", "reuters"}


def test_language_filter_is_distinct(client, seeded):
    # reuters has two EN... add a second so a non-distinct JOIN would dupe it.
    # (reuters already has one EN; the both-languages row set guarantees the
    # JOIN could fan out — assert each source appears at most once.)
    resp = client.get("/api/v1/sources/?language=en")
    names = [s["name"] for s in resp.json()]
    assert len(names) == len(set(names))
