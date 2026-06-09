"""PostgreSQL-based analytics queries using advanced SQL patterns.

Demonstrates window functions, CTEs, and GROUPING SETS for the
Relational Databases module. These complement the BigQuery analytics
by providing real-time queries against the operational database.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.constants.entity_filters import publisher_denylist_lower

# Entity types that are never real named entities (numbers, dates, etc.).
_NON_ENTITY_TYPES = (
    "NUMBER",
    "OTHER",
    "DATE",
    "PRICE",
    "ADDRESS",
    "PHONE_NUMBER",
)


def _lang_clause(language: str | None, *, col: str = "language") -> str:
    """Optional ``AND <col> = :language`` SQL fragment.

    Returns an empty string when no language filter is requested, so the same
    query text serves both the all-languages and per-language (EN/DE) cases.
    The matching ``:language`` bind is only added to the params dict when set.
    """
    return f"\n                  AND {col} = :language" if language else ""


def sentiment_rolling_average(
    db: Session, *, days: int = 30, window: int = 7, language: str | None = None
) -> list[dict[str, Any]]:
    """7-day rolling average sentiment using a window function.

    Uses AVG() OVER (ORDER BY ... ROWS BETWEEN) to smooth daily
    sentiment fluctuations, revealing underlying trends.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    params: dict[str, Any] = {"cutoff": cutoff, "window_size": window - 1}
    if language:
        params["language"] = language
    result = db.execute(
        text(f"""
            WITH daily AS (
                SELECT
                    DATE(published_at) AS day,
                    COUNT(*)           AS article_count,
                    AVG(sentiment_score) AS avg_sentiment
                FROM articles
                WHERE sentiment_score IS NOT NULL
                  AND published_at >= :cutoff{_lang_clause(language)}
                GROUP BY DATE(published_at)
            )
            SELECT
                day,
                article_count,
                ROUND(avg_sentiment::numeric, 4) AS avg_sentiment,
                ROUND(
                    AVG(avg_sentiment) OVER (
                        ORDER BY day
                        ROWS BETWEEN :window_size PRECEDING AND CURRENT ROW
                    )::numeric, 4
                ) AS rolling_avg
            FROM daily
            ORDER BY day
        """),
        params,
    )
    return [dict(row._mapping) for row in result]


def source_sentiment_ranked(
    db: Session, *, days: int = 30, language: str | None = None
) -> list[dict[str, Any]]:
    """Rank sources by average sentiment using RANK() window function.

    Uses a CTE to compute per-source stats, then RANK() OVER to
    assign a rank by avg sentiment (highest = most positive source).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    params: dict[str, Any] = {"cutoff": cutoff}
    if language:
        params["language"] = language
    result = db.execute(
        text(f"""
            WITH source_stats AS (
                SELECT
                    s.name          AS source_name,
                    COUNT(a.id)     AS article_count,
                    AVG(a.sentiment_score) AS avg_sentiment,
                    STDDEV(a.sentiment_score) AS sentiment_stddev
                FROM sources s
                JOIN articles a ON a.source_id = s.id
                WHERE a.sentiment_score IS NOT NULL
                  AND a.published_at >= :cutoff{_lang_clause(language, col="a.language")}
                GROUP BY s.name
                HAVING COUNT(a.id) >= 3
            )
            SELECT
                source_name,
                article_count,
                ROUND(avg_sentiment::numeric, 4) AS avg_sentiment,
                ROUND(sentiment_stddev::numeric, 4) AS sentiment_stddev,
                RANK() OVER (ORDER BY avg_sentiment DESC) AS positivity_rank
            FROM source_stats
            ORDER BY positivity_rank
        """),
        params,
    )
    return [dict(row._mapping) for row in result]


def sentiment_grouping_sets(
    db: Session, *, days: int = 30, language: str | None = None
) -> list[dict[str, Any]]:
    """Multi-dimensional sentiment breakdown using GROUPING SETS.

    Returns article counts and avg sentiment grouped by:
    - (category, sentiment_label) — per-category per-label
    - (category) — subtotal per category
    - (sentiment_label) — subtotal per label
    - () — grand total
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    params: dict[str, Any] = {"cutoff": cutoff}
    if language:
        params["language"] = language
    result = db.execute(
        text(f"""
            SELECT
                COALESCE(category, '(all)')         AS category,
                COALESCE(sentiment_label, '(all)')  AS sentiment_label,
                COUNT(*)                             AS article_count,
                ROUND(AVG(sentiment_score)::numeric, 4) AS avg_sentiment,
                GROUPING(category)                   AS is_category_total,
                GROUPING(sentiment_label)            AS is_label_total
            FROM articles
            WHERE sentiment_score IS NOT NULL
              AND published_at >= :cutoff{_lang_clause(language)}
            GROUP BY GROUPING SETS (
                (category, sentiment_label),
                (category),
                (sentiment_label),
                ()
            )
            ORDER BY is_category_total, is_label_total, category, sentiment_label
        """),
        params,
    )
    return [dict(row._mapping) for row in result]


def entity_momentum(
    db: Session, *, days: int = 14, language: str | None = None
) -> list[dict[str, Any]]:
    """Entity momentum: compare mention frequency this window vs the previous one.

    Uses two CTEs split at the window midpoint, then computes growth rate.
    Surfaces entities that are trending up or down.

    The windows key off ``article_entities.analyzed_at`` (when the entity was
    extracted in *our* pipeline), NOT ``articles.published_at``. Entity
    enrichment lags publication by days-to-weeks (the crawl/GCP-NL worker drains
    a backlog), so a ``published_at`` window over the last few days catches
    freshly-ingested articles that have not been entity-analyzed yet — returning
    empty. ``analyzed_at`` is also the semantically correct axis for "trending
    names": it reflects when a name surged in our analyzed coverage.

    Unlike the other analytics queries, the CTEs here don't reference ``articles``
    (they aggregate over ``entities`` + ``article_entities``). A ``language``
    filter therefore requires an extra ``JOIN articles`` to reach
    ``articles.language``; the join is added only when a language is requested,
    so the all-languages query is unchanged.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    midpoint = datetime.now(timezone.utc) - timedelta(days=days // 2)
    # Only reach into ``articles`` when filtering by language — keeps the default
    # (all-languages) plan identical to before this feature.
    lang_join = (
        "\n                JOIN articles a ON a.id = ae.article_id" if language else ""
    )
    lang_filter = "\n                  AND a.language = :language" if language else ""
    # Quality gate (shared with the BigQuery entity charts): keep only
    # Knowledge-Graph-resolved entities (wikipedia_url set), drop non-entity
    # types, and exclude publisher / wire-service / image-credit names that are
    # self-referential page furniture rather than news subjects.
    stmt = text(f"""
            WITH recent AS (
                SELECT
                    e.name          AS entity_name,
                    e.type          AS entity_type,
                    COUNT(ae.id)    AS mention_count
                FROM entities e
                JOIN article_entities ae ON ae.entity_id = e.id{lang_join}
                WHERE ae.analyzed_at >= :midpoint
                  AND e.wikipedia_url IS NOT NULL
                  AND e.type NOT IN :non_entity_types
                  AND LOWER(e.name) NOT IN :publisher_denylist{lang_filter}
                GROUP BY e.name, e.type
            ),
            previous AS (
                SELECT
                    e.name          AS entity_name,
                    e.type          AS entity_type,
                    COUNT(ae.id)    AS mention_count
                FROM entities e
                JOIN article_entities ae ON ae.entity_id = e.id{lang_join}
                WHERE ae.analyzed_at >= :cutoff
                  AND ae.analyzed_at < :midpoint
                  AND e.wikipedia_url IS NOT NULL
                  AND e.type NOT IN :non_entity_types
                  AND LOWER(e.name) NOT IN :publisher_denylist{lang_filter}
                GROUP BY e.name, e.type
            )
            SELECT
                COALESCE(r.entity_name, p.entity_name) AS entity_name,
                COALESCE(r.entity_type, p.entity_type) AS entity_type,
                COALESCE(r.mention_count, 0)            AS recent_mentions,
                COALESCE(p.mention_count, 0)            AS previous_mentions,
                ROUND(
                    CASE
                        WHEN COALESCE(p.mention_count, 0) = 0 THEN 100.0
                        ELSE (
                            (COALESCE(r.mention_count, 0) - p.mention_count)::numeric
                            / p.mention_count * 100
                        )
                    END, 2
                ) AS growth_pct
            FROM recent r
            FULL OUTER JOIN previous p
                ON r.entity_name = p.entity_name AND r.entity_type = p.entity_type
            WHERE COALESCE(r.mention_count, 0) + COALESCE(p.mention_count, 0) >= 3
            ORDER BY growth_pct DESC
        """).bindparams(
        bindparam("non_entity_types", expanding=True),
        bindparam("publisher_denylist", expanding=True),
    )
    exec_params: dict[str, Any] = {
        "cutoff": cutoff,
        "midpoint": midpoint,
        "non_entity_types": list(_NON_ENTITY_TYPES),
        "publisher_denylist": publisher_denylist_lower(),
    }
    if language:
        exec_params["language"] = language
    result = db.execute(stmt, exec_params)
    return [dict(row._mapping) for row in result]


def daily_category_sentiment_pivot(
    db: Session, *, days: int = 14, language: str | None = None
) -> list[dict[str, Any]]:
    """Daily sentiment per category using window functions for running totals.

    Uses a CTE for daily aggregation, then adds cumulative article count
    per category via SUM() OVER (PARTITION BY ... ORDER BY).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    params: dict[str, Any] = {"cutoff": cutoff}
    if language:
        params["language"] = language
    result = db.execute(
        text(f"""
            WITH daily_cat AS (
                SELECT
                    DATE(published_at)       AS day,
                    COALESCE(category, 'uncategorized') AS category,
                    COUNT(*)                 AS article_count,
                    AVG(sentiment_score)     AS avg_sentiment
                FROM articles
                WHERE sentiment_score IS NOT NULL
                  AND published_at >= :cutoff{_lang_clause(language)}
                GROUP BY DATE(published_at), category
            )
            SELECT
                day,
                category,
                article_count,
                ROUND(avg_sentiment::numeric, 4) AS avg_sentiment,
                SUM(article_count) OVER (
                    PARTITION BY category ORDER BY day
                ) AS cumulative_articles
            FROM daily_cat
            ORDER BY day, category
        """),
        params,
    )
    return [dict(row._mapping) for row in result]
