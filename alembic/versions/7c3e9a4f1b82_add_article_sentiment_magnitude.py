"""add article sentiment_magnitude

Denormalizes the GCP NL sentiment ``magnitude`` (emotional intensity, 0+) onto
``articles`` as a new nullable ``sentiment_magnitude`` column, mirroring the
existing ``sentiment_label`` / ``sentiment_score`` denormalization. The value
already exists per-provider on ``sentiment_analyses.magnitude``; copying the
primary provider's value onto the article lets the read path stay denormalized
(the article router deliberately does not serialize the ``sentiment_analyses``
relationship).

Additive and reversible: the column is nullable with no default, so existing
rows are unaffected (VADER-only articles legitimately stay NULL — VADER produces
no magnitude). A one-off backfill script populates historical GCP-NL articles.

Revision ID: 7c3e9a4f1b82
Revises: 2d60fa48c9ba
Create Date: 2026-06-09

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3e9a4f1b82"
down_revision: Union[str, None] = "2d60fa48c9ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the nullable sentiment_magnitude column to articles."""
    op.add_column(
        "articles",
        sa.Column("sentiment_magnitude", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Drop the sentiment_magnitude column."""
    op.drop_column("articles", "sentiment_magnitude")
