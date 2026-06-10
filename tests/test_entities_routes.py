"""Quality-gate coverage for the GET /api/v1/entities/ endpoint.

The endpoint must apply the same two-layer gate as the analytics entity charts:
Knowledge-Graph-resolved only (wikipedia_url IS NOT NULL) and excluding the
publisher denylist — so it can't leak generic nouns or publisher self-reference.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.article import Article
from app.models.article_entity import ArticleEntity
from app.models.entity import Entity
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


def _seed_entity(db, *, name: str, wiki: str | None, article: Article) -> None:
    ent = Entity(name=name, type="ORGANIZATION", wikipedia_url=wiki)
    db.add(ent)
    db.flush()
    db.add(ArticleEntity(article_id=article.id, entity_id=ent.id, salience=0.5))


def test_entities_endpoint_applies_quality_gate(client, test_db):
    src = Source(id=1, name="bbc")
    test_db.add(src)
    test_db.flush()
    art = Article(
        source_id=1,
        title="t",
        url="https://example.com/a",
        published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    test_db.add(art)
    test_db.flush()

    # Keep: real KG-resolved subject. Drop: no wiki_url (generic noun) + a
    # publisher that HAS a wiki_url but is on the denylist.
    _seed_entity(
        test_db, name="Tesla", wiki="https://en.wikipedia.org/wiki/Tesla", article=art
    )
    _seed_entity(test_db, name="investors", wiki=None, article=art)
    _seed_entity(
        test_db, name="BBC", wiki="https://en.wikipedia.org/wiki/BBC", article=art
    )
    test_db.commit()

    resp = client.get("/api/v1/entities/")
    assert resp.status_code == 200
    names = {e["name"] for e in resp.json()}
    assert names == {"Tesla"}
