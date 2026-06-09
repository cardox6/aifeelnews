"""PostgreSQL full-text search over articles.

A parallel, richer search path to the trigram substring search on ``/articles/``
(migration a3f1c2d4e5b6): this queries a generated ``tsvector`` column with
``websearch_to_tsquery`` and ranks hits by ``ts_rank``, giving stemming,
stop-words and phrase/boolean operators across the weighted title (A) +
description (B).

There are TWO vector columns — ``search_vector`` (English config, migration
b4e2d5c6f7a8) and ``search_vector_de`` (German config, migration c5f3a6b7d8e9) —
because a single generated column can't pick its config per row (Postgres
requires an immutable generation expression). German articles must be queried
against the German-stemmed column or inflected words ("Fußball", "Wetter") miss.

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

# Per-language FTS settings: the generated tsvector column to match against and
# the text-search config to parse the query with. Both must agree (a German query
# only matches the German-stemmed column). Keyed by ISO 639-1; defaults to English.
# These are fixed literals interpolated into SQL — NEVER user input — so the
# column name and config name are safe to format in.
_FTS = {
    "en": ("search_vector", "english"),
    "de": ("search_vector_de", "german"),
}


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

    ``language`` (ISO 639-1) both filters to that language and selects the
    matching FTS column + config (``search_vector_de`` / ``german`` for ``de``),
    so a German query stems correctly. Defaults to the English pair for any
    unknown/absent code.
    """
    # Column + config are fixed literals from the allowlist above (never user
    # input), so they're safe to interpolate. ``:q`` stays a bind parameter.
    column, cfg = _FTS.get(language or "en", _FTS["en"])
    predicate = f"{column} @@ websearch_to_tsquery('{cfg}', :q)"
    rank = f"ts_rank({column}, websearch_to_tsquery('{cfg}', :q)) DESC"

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
