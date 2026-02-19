"""add entities, article_entities, and article_categories tables

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5g6
Create Date: 2026-02-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Canonical entities lookup table (no FKs to other new tables)
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("wikipedia_url", sa.String(length=1000), nullable=True),
        sa.Column("mid", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_entities_id"), "entities", ["id"])
    op.create_index("ix_entities_name_type", "entities", ["name", "type"], unique=True)
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_type", "entities", ["type"])

    # 2. Article-Entity M2M association table
    op.create_table(
        "article_entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("salience", sa.Float(), nullable=False),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_article_entities_id"), "article_entities", ["id"])
    op.create_index(
        "ix_article_entities_article_id", "article_entities", ["article_id"]
    )
    op.create_index("ix_article_entities_entity_id", "article_entities", ["entity_id"])
    op.create_index(
        "ix_article_entities_article_entity",
        "article_entities",
        ["article_id", "entity_id"],
        unique=True,
    )
    op.create_index("ix_article_entities_salience", "article_entities", ["salience"])

    # 3. Article categories (1:many)
    op.create_table(
        "article_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "analyzed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_article_categories_id"), "article_categories", ["id"])
    op.create_index(
        "ix_article_categories_article_id", "article_categories", ["article_id"]
    )
    op.create_index("ix_article_categories_name", "article_categories", ["name"])
    op.create_index(
        "ix_article_categories_confidence", "article_categories", ["confidence"]
    )


def downgrade() -> None:
    op.drop_table("article_categories")
    op.drop_table("article_entities")
    op.drop_table("entities")
