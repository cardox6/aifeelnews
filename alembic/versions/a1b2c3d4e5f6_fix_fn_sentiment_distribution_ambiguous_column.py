"""fix ambiguous column in fn_sentiment_distribution

The original definition in e1f2a3b4c5d6 declared an OUT column
``sentiment_label`` (via ``RETURNS TABLE``) and then used an unqualified
``sentiment_label`` reference inside the ``SELECT COUNT(*) INTO v_total``
block at the top of the body. PL/pgSQL resolves bare identifiers against
declared variables / OUT params *and* table columns, so it can't pick a
side and raises:

    ERROR:  column reference "sentiment_label" is ambiguous
    DETAIL: It could refer to either a PL/pgSQL variable or a table column.

The ``RETURN QUERY`` block lower down was already aliased (``FROM articles a``
... ``WHERE a.sentiment_label``) and worked; the bug was only the small
total-count query. Fix is to add the same table alias there, so every
column reference is qualified.

``CREATE OR REPLACE FUNCTION`` rewrites the stored definition in place
without dropping it — no dependent views/triggers are affected, no
recreate-on-rollback needed. The downgrade restores the original (buggy)
definition verbatim so the chain is reversible, matching the convention
used elsewhere in this project.

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-05-13 07:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_sentiment_distribution(
            p_days INTEGER DEFAULT 30
        )
        RETURNS TABLE (
            sentiment_label VARCHAR,
            article_count   BIGINT,
            percentage      NUMERIC
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_total BIGINT;
        BEGIN
            SELECT COUNT(*) INTO v_total
            FROM articles a
            WHERE a.sentiment_label IS NOT NULL
              AND a.published_at >= NOW() - (p_days || ' days')::INTERVAL;

            RETURN QUERY
            SELECT
                a.sentiment_label,
                COUNT(*)            AS article_count,
                ROUND(
                    COUNT(*)::NUMERIC / GREATEST(v_total, 1) * 100, 2
                )                   AS percentage
            FROM articles a
            WHERE a.sentiment_label IS NOT NULL
              AND a.published_at >= NOW() - (p_days || ' days')::INTERVAL
            GROUP BY a.sentiment_label
            ORDER BY article_count DESC;
        END;
        $$;
        """
    )


def downgrade() -> None:
    # Restore the original definition from e1f2a3b4c5d6 (which has the
    # ambiguous-column bug — included verbatim so the migration chain is
    # reversible). A real revert would only run as part of rolling the
    # whole chain back; calling the function at this revision will raise
    # ``ERROR:  column reference "sentiment_label" is ambiguous``, which
    # is the intended pre-fix behaviour.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_sentiment_distribution(
            p_days INTEGER DEFAULT 30
        )
        RETURNS TABLE (
            sentiment_label VARCHAR,
            article_count   BIGINT,
            percentage      NUMERIC
        )
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_total BIGINT;
        BEGIN
            SELECT COUNT(*) INTO v_total
            FROM articles
            WHERE sentiment_label IS NOT NULL
              AND published_at >= NOW() - (p_days || ' days')::INTERVAL;

            RETURN QUERY
            SELECT
                a.sentiment_label,
                COUNT(*)            AS article_count,
                ROUND(
                    COUNT(*)::NUMERIC / GREATEST(v_total, 1) * 100, 2
                )                   AS percentage
            FROM articles a
            WHERE a.sentiment_label IS NOT NULL
              AND a.published_at >= NOW() - (p_days || ' days')::INTERVAL
            GROUP BY a.sentiment_label
            ORDER BY article_count DESC;
        END;
        $$;
        """
    )
