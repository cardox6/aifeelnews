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


def search_articles(
    db: Session,
    *,
    q: str,
    skip: int = 0,
    limit: int = 20,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
) -> list[Article]:
    """Full-text search articles by ``q``, ranked by ts_rank (desc), then recency.

    ``q`` is parsed with ``websearch_to_tsquery`` — the user-facing grammar that
    accepts quoted "phrases", ``or``, and leading ``-`` for exclusion, and never
    raises on malformed input (unlike ``to_tsquery``). The same eager loads as
    the list endpoint are applied so the response shape matches ``ArticleRead``.
    """
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
        .filter(text("search_vector @@ websearch_to_tsquery('english', :q)"))
    )

    if published_after is not None:
        query = query.filter(Article.published_at >= published_after)
    if published_before is not None:
        query = query.filter(Article.published_at <= published_before)

    return list(
        query.order_by(
            text("ts_rank(search_vector, websearch_to_tsquery('english', :q)) DESC"),
            Article.published_at.desc(),
            Article.id.desc(),
        )
        .params(q=q)
        .offset(skip)
        .limit(limit)
        .all()
    )
