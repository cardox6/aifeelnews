"""add German full-text search_vector_de (tsvector) column + GIN index

Revision ID: c5f3a6b7d8e9
Revises: b4e2d5c6f7a8
Create Date: 2026-06-09 08:30:00.000000

Background
----------
Migration b4e2d5c6f7a8 added ``search_vector`` generated with the **English**
text-search config. The bilingual EN/DE work queries German articles with
``websearch_to_tsquery('german', ...)``, but matching a German query against an
English-stemmed vector fails for any word German stems differently ("Fußball",
"Wetter" miss; only identically-stemmed tokens like "Forschung" hit).

A single generated column can't pick the config per row — Postgres requires the
generation expression to be IMMUTABLE, and ``to_tsvector(<column>::regconfig, …)``
is not (the regconfig is resolved at runtime). So we add a **second** generated
column, ``search_vector_de``, stemmed with the ``german`` config. The search CRUD
then queries ``search_vector_de`` for German and ``search_vector`` for English,
giving full stemming + stop-words for both languages.

Design notes
------------
* Same ``GENERATED ALWAYS AS (...) STORED`` + weighted title(A)/description(B)
  shape as the English column, so it auto-syncs with no trigger.
* Like ``search_vector``, this column is **deliberately NOT mapped on the ORM
  ``Article`` model** — it's a Postgres-only object the SQLite test schema never
  needs, referenced only via raw ``text()`` in ``app/crud/search.py``. (Autogenerate
  would propose DROPping it because it's absent from ``Base.metadata`` — keep it.)
* The ``german`` text-search config ships with Postgres by default.

Postgres-only DDL (the SQLite test DB is built from ``Base.metadata`` via
``create_all``, never migrated), consistent with the sibling FTS migration.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5f3a6b7d8e9"
down_revision: Union[str, None] = "b4e2d5c6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE articles
        ADD COLUMN search_vector_de tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('german', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('german', coalesce(description, '')), 'B')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_articles_search_vector_de "
        "ON articles USING gin (search_vector_de)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_search_vector_de")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS search_vector_de")
