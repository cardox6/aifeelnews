"""add pg_trgm trigram index on articles.title for indexed substring search

Revision ID: a3f1c2d4e5b6
Revises: 7c3e9a4f1b82
Create Date: 2026-06-09 05:30:00.000000

Background
----------
``GET /api/v1/articles/?search=`` filters with ``title ILIKE '%term%'``. The
leading wildcard makes the match unindexable by a btree, so every search was a
sequential scan over the whole ``articles`` table.

The ``pg_trgm`` extension provides a GIN trigram index that *does* accelerate
``ILIKE '%term%'`` (and ``similarity()`` ranking). After this migration the same
query plans as a Bitmap Index Scan on ``ix_articles_title_trgm`` instead of a
Seq Scan. This closes the long-standing TODO in ``app/routers/articles.py``.

Postgres-only DDL (like every migration here — the SQLite test DB is built from
``Base.metadata`` via ``create_all``, never migrated). The extension and index
are no-ops on a non-Postgres engine, so this file is never executed there.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c2d4e5b6"
down_revision: Union[str, None] = "7c3e9a4f1b82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable trigram matching. IF NOT EXISTS keeps re-runs / shared databases
    # safe. Requires the role to have CREATE on the database (the Cloud SQL
    # app user does; pg_trgm ships with Postgres 14 — no superuser needed for
    # CREATE EXTENSION on a trusted extension).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # GIN trigram index: accelerates ILIKE '%term%' substring search and
    # similarity()/word_similarity() ranking on the title.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_articles_title_trgm "
        "ON articles USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_title_trgm")
    # Intentionally NOT dropping the extension: other objects (future FTS work,
    # other trigram indexes) may come to depend on it, and DROP EXTENSION would
    # cascade. Leaving it installed is harmless and the safe default.
