"""add bookmark indexes, views, stored functions, and triggers

Revision ID: e1f2a3b4c5d6
Revises: d8e9f0a1b2c3
Create Date: 2026-03-16 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── B.1: Bookmark FK indexes (fixes full-table scans) ──────────────
    op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])
    op.create_index("ix_bookmarks_article_id", "bookmarks", ["article_id"])

    # ── B.3: PostgreSQL Views ──────────────────────────────────────────
    # View 1: Article summary with source name and sentiment
    op.execute("""
        CREATE OR REPLACE VIEW v_article_summary AS
        SELECT
            a.id            AS article_id,
            a.title,
            s.name          AS source_name,
            a.published_at,
            a.sentiment_label,
            a.sentiment_score,
            a.category,
            a.country,
            a.language
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        ORDER BY a.published_at DESC;
    """)

    # View 2: Source statistics (article count, avg sentiment, date range)
    op.execute("""
        CREATE OR REPLACE VIEW v_source_stats AS
        SELECT
            s.id                           AS source_id,
            s.name                         AS source_name,
            COUNT(a.id)                    AS article_count,
            ROUND(AVG(a.sentiment_score)::numeric, 4) AS avg_sentiment,
            MIN(a.published_at)            AS earliest_article,
            MAX(a.published_at)            AS latest_article
        FROM sources s
        LEFT JOIN articles a ON a.source_id = s.id
        GROUP BY s.id, s.name;
    """)

    # View 3: Daily sentiment aggregation
    op.execute("""
        CREATE OR REPLACE VIEW v_daily_sentiment AS
        SELECT
            DATE(a.published_at)          AS day,
            COUNT(*)                      AS article_count,
            ROUND(AVG(a.sentiment_score)::numeric, 4) AS avg_sentiment,
            COUNT(*) FILTER (WHERE a.sentiment_label = 'positive')  AS positive_count,
            COUNT(*) FILTER (WHERE a.sentiment_label = 'negative')  AS negative_count,
            COUNT(*) FILTER (WHERE a.sentiment_label = 'neutral')   AS neutral_count
        FROM articles a
        WHERE a.sentiment_score IS NOT NULL
        GROUP BY DATE(a.published_at)
        ORDER BY day DESC;
    """)

    # View 4: Trending entities (top entities by recent article mentions)
    op.execute("""
        CREATE OR REPLACE VIEW v_trending_entities AS
        SELECT
            e.id                            AS entity_id,
            e.name                          AS entity_name,
            e.type                          AS entity_type,
            COUNT(ae.article_id)            AS article_count,
            SUM(ae.mention_count)           AS total_mentions,
            ROUND(AVG(ae.salience)::numeric, 4) AS avg_salience
        FROM entities e
        JOIN article_entities ae ON ae.entity_id = e.id
        JOIN articles a ON a.id = ae.article_id
        WHERE a.published_at >= NOW() - INTERVAL '7 days'
        GROUP BY e.id, e.name, e.type
        ORDER BY article_count DESC, avg_salience DESC;
    """)

    # ── B.4: Stored Functions (PL/pgSQL) ───────────────────────────────
    # Function 1: Sentiment distribution for a given date range
    op.execute("""
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
    """)

    # Function 2: Source performance (articles, sentiment, entity richness)
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_source_performance(
            p_days INTEGER DEFAULT 30
        )
        RETURNS TABLE (
            source_name      VARCHAR,
            article_count    BIGINT,
            avg_sentiment    NUMERIC,
            entity_richness  NUMERIC,
            crawl_success_rate NUMERIC
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                s.name                          AS source_name,
                COUNT(DISTINCT a.id)            AS article_count,
                ROUND(AVG(a.sentiment_score)::NUMERIC, 4) AS avg_sentiment,
                ROUND(
                    AVG(sub_ent.entity_count)::NUMERIC, 2
                )                               AS entity_richness,
                ROUND(
                    COUNT(DISTINCT cj.id) FILTER (WHERE cj.status = 'SUCCESS')::NUMERIC
                    / GREATEST(COUNT(DISTINCT cj.id), 1) * 100, 2
                )                               AS crawl_success_rate
            FROM sources s
            JOIN articles a ON a.source_id = s.id
            LEFT JOIN crawl_jobs cj ON cj.article_id = a.id
            LEFT JOIN LATERAL (
                SELECT COUNT(*) AS entity_count
                FROM article_entities ae
                WHERE ae.article_id = a.id
            ) sub_ent ON TRUE
            WHERE a.published_at >= NOW() - (p_days || ' days')::INTERVAL
            GROUP BY s.name
            ORDER BY article_count DESC;
        END;
        $$;
    """)

    # ── B.5: Triggers ──────────────────────────────────────────────────
    # Trigger 1: Auto-update source.updated_at when a new article is inserted
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_fn_update_source_timestamp()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            UPDATE sources SET updated_at = NOW() WHERE id = NEW.source_id;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_update_source_timestamp
        AFTER INSERT ON articles
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_update_source_timestamp();
    """)

    # Trigger 2: Prevent duplicate bookmarks (same user + article)
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_fn_prevent_duplicate_bookmark()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM bookmarks
                WHERE user_id = NEW.user_id AND article_id = NEW.article_id
            ) THEN
                RAISE EXCEPTION 'Duplicate bookmark: user_id=% already bookmarked article_id=%',
                    NEW.user_id, NEW.article_id;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_prevent_duplicate_bookmark
        BEFORE INSERT ON bookmarks
        FOR EACH ROW
        EXECUTE FUNCTION trg_fn_prevent_duplicate_bookmark();
    """)


def downgrade() -> None:
    # Triggers
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_duplicate_bookmark ON bookmarks;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_prevent_duplicate_bookmark();")
    op.execute("DROP TRIGGER IF EXISTS trg_update_source_timestamp ON articles;")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_update_source_timestamp();")

    # Stored functions
    op.execute("DROP FUNCTION IF EXISTS fn_source_performance(INTEGER);")
    op.execute("DROP FUNCTION IF EXISTS fn_sentiment_distribution(INTEGER);")

    # Views
    op.execute("DROP VIEW IF EXISTS v_trending_entities;")
    op.execute("DROP VIEW IF EXISTS v_daily_sentiment;")
    op.execute("DROP VIEW IF EXISTS v_source_stats;")
    op.execute("DROP VIEW IF EXISTS v_article_summary;")

    # Bookmark indexes
    op.drop_index("ix_bookmarks_article_id", "bookmarks")
    op.drop_index("ix_bookmarks_user_id", "bookmarks")
