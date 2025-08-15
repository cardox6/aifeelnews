"""add author column to articles

Revision ID: 6f112f84a54a
Revises: ae63b0495c28
Create Date: 2025-07-25 08:47:38.737078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f112f84a54a'
down_revision: Union[str, None] = 'ae63b0495c28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('articles',
        sa.Column('author', sa.Text(), nullable=True)
    )
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('articles', 'author')
    pass
