"""reconcile sources schema with model

Aligns the live ``sources`` table with the SQLAlchemy model so
``alembic revision --autogenerate`` produces a clean (empty) diff. Two
pre-existing, cosmetic drifts:

1. The model declares ``name`` with ``unique=True, index=True`` (a unique
   INDEX ``ix_sources_name``), but the initial migration created a unique
   CONSTRAINT ``sources_name_key``. Both enforce uniqueness identically — this
   only swaps the expression so it matches the model.
2. The model's ``comment=`` text on ``name`` / ``created_at`` / ``updated_at``
   was never written into a migration, so the live columns have no comments.

No behavioural change: uniqueness on ``name`` is enforced before and after, and
column comments are metadata only. Fully reversible.

Revision ID: 2d60fa48c9ba
Revises: 54bff216cdb7
Create Date: 2026-06-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2d60fa48c9ba"
down_revision: Union[str, None] = "54bff216cdb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add column comments and replace the unique constraint with a unique index."""
    op.alter_column(
        "sources",
        "name",
        existing_type=sa.VARCHAR(length=255),
        comment="Mediastack source identifier (e.g., 'bbc', 'cnn', 'independent')",
        existing_nullable=False,
    )
    op.alter_column(
        "sources",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="When the source was added to our system",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "sources",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="When the source was last updated",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.drop_constraint("sources_name_key", "sources", type_="unique")
    op.create_index(op.f("ix_sources_name"), "sources", ["name"], unique=True)


def downgrade() -> None:
    """Restore the unique constraint and drop the column comments."""
    op.drop_index(op.f("ix_sources_name"), table_name="sources")
    op.create_unique_constraint("sources_name_key", "sources", ["name"])
    op.alter_column(
        "sources",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment=None,
        existing_comment="When the source was last updated",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "sources",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment=None,
        existing_comment="When the source was added to our system",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "sources",
        "name",
        existing_type=sa.VARCHAR(length=255),
        comment=None,
        existing_comment="Mediastack source identifier (e.g., 'bbc', 'cnn', 'independent')",
        existing_nullable=False,
    )
