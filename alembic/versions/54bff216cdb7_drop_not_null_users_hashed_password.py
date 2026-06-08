"""drop not null users hashed_password

Aligns the DB with the ORM model. The initial migration 033994d9eedb created
``users.hashed_password`` as NOT NULL, but the model later loosened it to
``Mapped[Optional[str]]`` without a follow-up ALTER (6ad9a0b7d4b7 punted because
SQLite cannot ALTER COLUMN). Firebase-federated users legitimately have no
password, so the model is correct and the column should be nullable.

Revision ID: 54bff216cdb7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08 14:31:53.437498

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "54bff216cdb7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    # Backfill any NULLs (Firebase users) before restoring NOT NULL, so the
    # downgrade is reversible on real data.
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(),
        nullable=False,
    )
