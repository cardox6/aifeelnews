"""PostgreSQL full-text search over articles.

A parallel, richer search path to the trigram substring search on ``/articles/``
(migration a3f1c2d4e5b6): this queries the generated ``search_vector`` tsvector
column (migration b4e2d5c6f7a8) with ``websearch_to_tsquery`` and ranks hits by
``ts_rank``, giving stemming, stop-words and phrase/boolean operators across the
weighted title (A) + description (B).

Postgres-only — the ``@@`` operator, ``websearch_to_tsquery`` and ``ts_rank`` do
not exist on SQLite. The caller (the ``/articles/search`` route) is reached only
on the deployed Postgres stack; the SQLite test suite never hits this module
(its tests are ``@pytest.mark.postgres``).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload, subqueryload

from app.models.article import Article
from app.models.article_entity import ArticleEntity

# Postgres FTS text-search configurations, keyed by article language. Both ship
# with Postgres by default. The value is interpolated into the tsquery SQL, so it
# MUST come from this fixed allowlist — never from user input.
_FTS_CONFIG = {"en": "english", "de": "german"}


def search_articles(
    db: Session,
    *,
    q: str,
    skip: int = 0,
    limit: int = 20,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
    language: Optional[str] = None,
) -> list[Article]:
    """Full-text search articles by ``q``, ranked by ts_rank (desc), then recency.

    ``q`` is parsed with ``websearch_to_tsquery`` — the user-facing grammar that
    accepts quoted "phrases", ``or``, and leading ``-`` for exclusion, and never
    raises on malformed input (unlike ``to_tsquery``). The same eager loads as
    the list endpoint are applied so the response shape matches ``ArticleRead``.

    ``language`` (ISO 639-1) both filters to that language and selects the FTS
    text-search config (``german`` stemming/stop-words for ``de``), so a German
    query stems correctly. It defaults to ``english`` for any unknown/absent code.
    """
    # The text-search config name is a fixed literal chosen from the allowlist
    # above — safe to interpolate into the SQL. ``:q`` stays a bind parameter.
    cfg = _FTS_CONFIG.get(language or "en", "english")
    predicate = f"search_vector @@ websearch_to_tsquery('{cfg}', :q)"
    rank = f"ts_rank(search_vector, websearch_to_tsquery('{cfg}', :q)) DESC"

    # The FTS predicate and rank reference the Postgres-only search_vector column
    # via text() (it is intentionally not an ORM attribute). The :q bind is set
    # once with .params() and reused by both the filter and the ORDER BY rank.
    query = (
        db.query(Article)
        .options(
            joinedload(Article.source),
            subqueryload(Article.article_entities).joinedload(ArticleEntity.entity),
            subqueryload(Article.article_categories),
        )
        .filter(text(predicate))
    )

    if language is not None:
        query = query.filter(Article.language == language)
    if published_after is not None:
        query = query.filter(Article.published_at >= published_after)
    if published_before is not None:
        query = query.filter(Article.published_at <= published_before)

    return list(
        query.order_by(
            text(rank),
            Article.published_at.desc(),
            Article.id.desc(),
        )
        .params(q=q)
        .offset(skip)
        .limit(limit)
        .all()
    )
