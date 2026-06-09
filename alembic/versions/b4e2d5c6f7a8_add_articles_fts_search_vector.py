"""add full-text search_vector (tsvector) column + GIN index on articles

Revision ID: b4e2d5c6f7a8
Revises: a3f1c2d4e5b6
Create Date: 2026-06-09 06:30:00.000000

Background
----------
PR #167 added trigram (pg_trgm) substring search + ranking on ``title``. This
adds a parallel **full-text** search path: a generated ``tsvector`` column over
weighted ``title`` (weight A) + ``description`` (weight B), GIN-indexed, queried
via ``websearch_to_tsquery`` and ranked with ``ts_rank``. This gives multi-field
linguistic ranking (stemming, stop-words, phrase + boolean operators) that
trigram matching can't, and powers the new ``GET /api/v1/articles/search`` route.

Design notes
------------
* ``GENERATED ALWAYS AS (...) STORED`` (Postgres 12+) keeps the vector in sync
  automatically — no trigger needed, unlike the classic tsvector pattern.
* ``coalesce(..., '')`` so a NULL description doesn't null the whole vector.
* The column is **deliberately NOT mapped on the ORM ``Article`` model**: it's a
  Postgres-only DB object (like the views/functions in migration e1f2a3b4c5d6),
  the SQLite test schema never needs it, and ``ArticleRead`` declares its fields
  explicitly so the vector can never leak into an API response. The search CRUD
  references it through raw ``text()`` SQL. (If you ever run
  ``alembic revision --autogenerate``, it will propose DROPping this column
  because it's absent from ``Base.metadata`` — keep it; this project hand-writes
  migrations.)

Postgres-only DDL (the SQLite test DB is built from ``Base.metadata`` via
``create_all``, never migrated), consistent with every other migration here.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e2d5c6f7a8"
down_revision: Union[str, None] = "a3f1c2d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE articles
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'B')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_articles_search_vector "
        "ON articles USING gin (search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_search_vector")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS search_vector")
