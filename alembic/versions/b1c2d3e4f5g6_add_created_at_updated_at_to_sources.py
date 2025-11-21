"""add created_at and updated_at to sources table

Revision ID: b1c2d3e4f5g6
Revises: 9f9cfecf9cb7
Create Date: 2025-11-21 15:22:05.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5g6"
down_revision: Union[str, None] = "9f9cfecf9cb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add created_at and updated_at columns to sources table."""
    # Add created_at column with default value
    op.add_column(
        "sources",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Add updated_at column with default value
    op.add_column(
        "sources",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Remove created_at and updated_at columns from sources table.
    """
    op.drop_column("sources", "updated_at")
    op.drop_column("sources", "created_at")
