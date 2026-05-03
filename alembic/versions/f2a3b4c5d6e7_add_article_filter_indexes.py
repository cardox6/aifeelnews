"""add article filter indexes

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-03 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Filter columns on /articles/ — supports the sentiment/category/source
    # filters and FK-join performance for source_id lookups.
    op.create_index("ix_articles_sentiment_label", "articles", ["sentiment_label"])
    op.create_index("ix_articles_category", "articles", ["category"])
    op.create_index("ix_articles_source_id", "articles", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_articles_source_id", table_name="articles")
    op.drop_index("ix_articles_category", table_name="articles")
    op.drop_index("ix_articles_sentiment_label", table_name="articles")
