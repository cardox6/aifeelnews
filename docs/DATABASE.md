# Database — aiFeelNews

PostgreSQL 14, accessed through SQLAlchemy 2.0 (`Mapped[]` typed ORM) and managed with Alembic. Ten tables, two many-to-many relationships (`bookmarks` and `article_entities`), and a layer of database objects — views, stored functions, and triggers — that push aggregation logic into the database where it belongs.

This doc covers the operational concerns: setup, migrations, schema objects, optimization patterns, and the data lifecycle. The full schema (table-by-table column listing, cardinality, index map) lives in [ER_Diagram.md](ER_Diagram.md).

---

## 1. Local Setup

**Prereqs:** Python 3.13, PostgreSQL 14, Docker (optional).

```bash
# 1. Install Python deps
pip install -r requirements.txt

# 2. Configure env
cat > .env <<'EOF'
ENV=local
LOCAL_DATABASE_URL=postgresql://aifeelnews:devpass@localhost:5432/aifeelnews
ARTICLE_CONTENT_TTL_HOURS=168
EOF

# 3. Start PostgreSQL (or use docker-compose)
docker run -d --name aifeelnews-pg \
  -e POSTGRES_USER=aifeelnews -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=aifeelnews -p 5432:5432 postgres:14

# 4. Run migrations
alembic upgrade head

# 5. Seed with one ingestion run
python -m app.jobs.run_ingestion

# 6. Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Full stack via Docker:** `docker-compose up --build` — brings up PostgreSQL, the FastAPI web service, the worker, and the scheduler in one shot.

---

## 2. Migrations

Nine migrations, applied in order. Run `alembic upgrade head` to apply, `alembic downgrade -1` to roll back the most recent one.

| # | Revision | Summary |
|---|----------|---------|
| 1 | `033994d9eedb` | Initial schema — `articles`, `sources`, `users`, `bookmarks` |
| 2 | `a25a4e6750e1` | Pydantic v2 schema fixes |
| 3 | `ae63b0495c28` | Post-Docker-review cleanup |
| 4 | `9f9cfecf9cb7` | Add `crawl_jobs`, `article_contents`, `sentiment_analyses` |
| 5 | `6ad9a0b7d4b7` | Add `firebase_uid` to `users` |
| 6 | `b1c2d3e4f5g6` | Add `created_at`, `updated_at` to `sources` |
| 7 | `c7d8e9f0a1b2` | Add `entities`, `article_entities`, `article_categories` |
| 8 | `d8e9f0a1b2c3` | Add `mention_count` to `article_entities` |
| 9 | `e1f2a3b4c5d6` | Bookmark FK indexes + views, stored functions, triggers |

---

## 3. Database Objects

Pushing aggregation, validation, and integrity logic into the database where it belongs. All defined in [migration `e1f2a3b4c5d6`](../alembic/versions/e1f2a3b4c5d6_add_db_objects_views_functions_triggers.py).

### 3.1 Views

Four views ([migration:25-91](../alembic/versions/e1f2a3b4c5d6_add_db_objects_views_functions_triggers.py#L25-L91)):

| View | Purpose |
|------|---------|
| `v_article_summary` | Articles joined with source name + sentiment, ordered by published date |
| `v_source_stats` | Per-source article count, average sentiment, date range |
| `v_daily_sentiment` | Daily article counts split by positive/negative/neutral |
| `v_trending_entities` | Entities with most mentions in the last 7 days |

```sql
-- Example: top 5 trending entities right now
SELECT entity_name, entity_type, article_count, total_mentions
FROM v_trending_entities
LIMIT 5;
```

### 3.2 Stored Functions

Two PL/pgSQL functions ([migration:93-170](../alembic/versions/e1f2a3b4c5d6_add_db_objects_views_functions_triggers.py#L93-L170)) — both parameterised by a day window for flexible analytics:

| Function | Returns |
|----------|---------|
| `fn_sentiment_distribution(p_days INT)` | Sentiment label, article count, percentage of total |
| `fn_source_performance(p_days INT)` | Per-source articles, avg sentiment, entity richness, crawl success rate |

```sql
-- Sentiment breakdown for the last 7 days
SELECT * FROM fn_sentiment_distribution(7);

-- Source scorecard for the last 30 days
SELECT * FROM fn_source_performance(30);
```

### 3.3 Triggers

Two triggers ([migration:172-215](../alembic/versions/e1f2a3b4c5d6_add_db_objects_views_functions_triggers.py#L172-L215)) enforcing invariants the application layer cannot reliably guarantee:

| Trigger | When | Effect |
|---------|------|--------|
| `trg_update_source_timestamp` | `AFTER INSERT` on `articles` | Updates `sources.updated_at = NOW()` |
| `trg_prevent_duplicate_bookmark` | `BEFORE INSERT` on `bookmarks` | Raises an exception if `(user_id, article_id)` already bookmarked |

The duplicate-bookmark trigger is a defence-in-depth measure: a `UNIQUE` constraint would also work, but the trigger gives a clearer error message and is easy to extend with additional validation later.

---

## 4. Optimization Examples

### 4.1 N+1 Query Fix on `GET /articles/`

Lazy-loading `Article.source`, `Article.sentiment_analyses`, `Article.article_entities`, and `Article.article_categories` triggers a separate round-trip per article. With 40 articles in the feed and 4 lazy relationships, a naive implementation makes ~160 extra queries per response.

The fix uses SQLAlchemy eager loading with the right strategy per relationship — see [app/routers/articles.py:14-30](../app/routers/articles.py#L14-L30):

```python
db.query(ArticleModel)
  .options(
      joinedload(ArticleModel.source),                # 1:1 -> JOIN
      joinedload(ArticleModel.sentiment_analyses),    # small N -> JOIN
      subqueryload(ArticleModel.article_entities)     # large N -> separate query
        .joinedload(ArticleEntity.entity),
      subqueryload(ArticleModel.article_categories),
  )
  .order_by(ArticleModel.published_at.desc())
  .limit(limit)
```

`joinedload` is right for 1:1 / low-cardinality relationships; `subqueryload` is right for high-cardinality ones (entities, categories) to avoid Cartesian explosion.

### 4.2 Bookmark Foreign-Key Indexes

Bookmarks are looked up by `user_id` (list a user's bookmarks) and by `article_id` (count how many users bookmarked an article). PostgreSQL does not auto-index FK columns — without explicit indexes, both queries scan the full table. Added in [migration:22-23](../alembic/versions/e1f2a3b4c5d6_add_db_objects_views_functions_triggers.py#L22-L23):

```sql
CREATE INDEX ix_bookmarks_user_id ON bookmarks (user_id);
CREATE INDEX ix_bookmarks_article_id ON bookmarks (article_id);
```

### 4.3 Advanced SQL Patterns

The CRUD module [app/crud/analytics.py](../app/crud/analytics.py) uses the right SQL pattern for each analytics question. Each function is a single round-trip — heavy lifting stays in the database.

**Window functions — rolling averages and ranks:**
- `sentiment_rolling_average()` ([analytics.py:40-44](../app/crud/analytics.py#L40-L44)) — `AVG() OVER (ORDER BY day ROWS BETWEEN N PRECEDING AND CURRENT ROW)` smooths daily sentiment into a 7-day rolling average. Window functions are the right tool when you need per-row aggregates that depend on neighbouring rows.
- `source_sentiment_ranked()` ([analytics.py:81](../app/crud/analytics.py#L81)) — `RANK() OVER (ORDER BY avg_sentiment DESC)` ranks sources by average sentiment, letting the database do the ordering once instead of fetching everything and sorting in Python.

**CTEs — multi-step queries that read top-down:**
- `entity_momentum()` ([analytics.py:134-156](../app/crud/analytics.py#L134-L156)) — two CTEs (`recent`, `previous`) compute mention counts for two adjacent time windows, then a `FULL OUTER JOIN` produces growth rates. CTEs make the query's intent obvious without temporary tables.

**GROUPING SETS — multi-dimensional aggregation in one pass:**
- `sentiment_grouping_sets()` ([analytics.py:112-117](../app/crud/analytics.py#L112-L117)) — produces per-(category, label) counts plus per-category subtotals plus per-label subtotals plus a grand total in a single query, instead of running four separate `GROUP BY` queries and stitching the results.

### 4.4 Index Inventory

Composite and performance indexes are listed in [ER_Diagram.md § Composite & Performance Indexes](ER_Diagram.md#composite--performance-indexes). Highlights: `entities (name, type)` UNIQUE for canonical deduplication, `article_entities (article_id, entity_id)` UNIQUE preventing duplicate mentions, and `article_contents (expires_at)` for the TTL cleanup job.

---

## 4A. Transactions and ACID

The application uses SQLAlchemy 2.0 sessions configured with `autocommit=False, autoflush=False` ([app/database.py:32-33](../app/database.py#L32-L33)). Each request scope yields a session via `get_db()` ([app/database.py:49-57](../app/database.py#L49-L57)); the route handler runs inside it; the session is closed in a `finally` block — pending changes are implicitly rolled back on any unhandled exception.

**Atomicity policies by component:**

| Component | Commit policy | Rationale |
|-----------|---------------|-----------|
| API write routes ([app/routers/bookmarks.py](../app/routers/bookmarks.py), [app/routers/sources.py](../app/routers/sources.py), [app/deps/auth.py](../app/deps/auth.py)) | Per-request | Single logical operation per HTTP request. The implicit transaction commits at the end of the handler. |
| Batch ingest job ([app/jobs/ingest_articles.py](../app/jobs/ingest_articles.py)) | Per-batch | Whole-batch atomicity — partial inserts on failure are undesirable. The implicit transaction rolls back the entire batch if any insert fails the URL UNIQUE check. |
| Crawl worker ([app/jobs/crawl_worker.py](../app/jobs/crawl_worker.py)) | Per-article | Bounds the work lost on worker crash to one article. Status updates commit at each decision point so a retry can resume. |
| TTL cleanup ([app/utils/cleanup.py](../app/utils/cleanup.py), [app/jobs/ttl_cleanup.py](../app/jobs/ttl_cleanup.py)) | Per-job | Idempotent bulk DELETEs; partial completion is harmless on retry. |

**Constraint enforcement and HTTP-status mapping:**

The `trg_prevent_duplicate_bookmark` trigger raises `IntegrityError` on a duplicate `(user_id, article_id)`. The bookmark create handler catches that exception, calls `db.rollback()`, and translates it into HTTP 409 Conflict ([app/routers/bookmarks.py:16-36](../app/routers/bookmarks.py#L16-L36)):

```python
try:
    db.commit()
except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="Bookmark already exists for this article")
```

This is the textbook ACID example for the project: a database-layer constraint (the trigger) is the source of truth for "no duplicates"; the application layer treats `IntegrityError` as the canonical signal and maps it to the correct HTTP semantics. Pre-checking with a `SELECT` before the `INSERT` would still need the same trigger as the safety net for concurrent requests, so the code skips the pre-check and relies on the trigger directly.

UNIQUE constraints on `articles.url`, `sources.name`, and `entities (name, type)` are enforced at the database layer; application code does not assume uniqueness from pre-`SELECT`s alone.

**Session aborted-state handling:**

After a failed `db.commit()`, a SQLAlchemy session is in `PendingRollbackError` state — any subsequent `commit()` will fail until `db.rollback()` is called. The crawl-worker exception handlers ([app/jobs/crawl_worker.py:456-494](../app/jobs/crawl_worker.py#L456-L494)) call `db.rollback()` *before* mutating `crawl_job` and re-committing the failure record, in this order:

1. `db.rollback()` — clear the aborted session.
2. Set `crawl_job.status = FAILED`, `error_code`, `error_message`.
3. `db.commit()` — record the failure.

Without step 1 the second commit propagates, the job stays in its prior status (often `IN_PROGRESS`), and the worker retries it on the next tick — which is the same poisoned job — forever. Setting the fields before the rollback would also be wrong, because the rollback would discard the assignments.

---

## 5. Data Lifecycle

The high-level pipeline is in [ER_Diagram.md § Data Lifecycle](ER_Diagram.md#data-lifecycle). What follows are the operational details — frequencies, configurations, and what is **not** stored.

### 5.1 Ingestion Cadence

Cloud Scheduler triggers `POST /api/v1/trigger-ingestion` every 8 hours ([infra/main.tf:148-166](../infra/main.tf#L148-L166)). A typical run ingests 50–200 articles depending on the active Mediastack categories. Articles are deduplicated by URL before insert, so re-runs are idempotent.

### 5.2 Content Truncation (Data Minimisation)

Crawled article bodies are capped at **1024 characters** at write time, see [app/models/article_content.py:20](../app/models/article_content.py#L20). The original byte length is retained in `content_length` for analytics, but the full body is never persisted. This is a deliberate data-minimisation choice: enough text for sentiment and entity analysis, not enough to constitute republication.

### 5.3 TTL Configuration and Cleanup

Article content is short-lived. The TTL is configured via `ARTICLE_CONTENT_TTL_HOURS` (default **168 = 7 days**, [app/config/ingestion.py:15](../app/config/ingestion.py#L15)). Each row's `expires_at` is set at ingest time by [app/utils/ttl.py:8-17](../app/utils/ttl.py#L8-L17):

```python
expiry = now + timedelta(hours=settings.ARTICLE_CONTENT_TTL_HOURS)
```

The cleanup job [app/utils/cleanup.py:14-50](../app/utils/cleanup.py#L14-L50) deletes rows where `expires_at <= now()`, runs daily via Cloud Scheduler against `POST /api/v1/cleanup` ([infra/main.tf:168-186](../infra/main.tf#L168-L186)), and uses the `ix_article_contents_expires_at` index for efficiency.

### 5.4 Crawl Job Retention

Terminal-state crawl jobs (`SUCCESS`, `FAILED`, `FORBIDDEN_BY_ROBOTS`) older than 7 days are pruned by `cleanup_old_crawl_jobs()` ([app/utils/cleanup.py:53-93](../app/utils/cleanup.py#L53-L93)). Active jobs (`PENDING`, `IN_PROGRESS`, `RATE_LIMITED`) are never touched by the cleanup job — they stay until the worker resolves them.

### 5.5 Cascade Deletes

`ON DELETE CASCADE` from every child table to its parent FK ensures referential integrity. The full cascade map is in [ER_Diagram.md § Cascade Delete Strategy](ER_Diagram.md#cascade-delete-strategy).

### 5.6 What is *Not* Stored

A short list, since the assessment cares about it:

- **Full article HTML** — only the truncated 1024-char text body
- **Raw NLP API responses** — only the extracted sentiment score, entity rows, and category rows
- **User PII** beyond `email` and `firebase_uid`
- **Passwords** — Firebase handles auth; we only store the verified UID
- **Mediastack API responses** beyond what gets normalised into `articles`

### 5.7 BigQuery Export

PostgreSQL is the operational store; BigQuery is the analytics warehouse. Sentiment events, entity events, and category events stream to BigQuery for long-term aggregation, partitioned by ingestion date and clustered for fast filtered scans (schema in [infra/main.tf:201-324](../infra/main.tf#L201-L324)). PostgreSQL is free to retain only what's needed for the live API.

---

## 6. Backup & Recovery

Cloud SQL is configured with **daily automated backups at 03:00 UTC** and **point-in-time recovery enabled** ([infra/main.tf:75-79](../infra/main.tf#L75-L79)). PITR replays write-ahead-log segments retained on the backup, so the recovery point can be a specific timestamp within the retention window — not just the last nightly snapshot. Deletion protection is on, so the instance cannot be removed by accident.

Restore from the latest backup:

```bash
gcloud sql backups restore <BACKUP_ID> \
  --restore-instance=aifeelnews-db
```

PITR clone to a fresh instance at a specific moment:

```bash
gcloud sql instances clone aifeelnews-db aifeelnews-db-clone \
  --point-in-time='2026-05-03T10:00:00.000Z'
```

The clone-then-promote flow is the safer path versus restoring in place: the clone is verified, then the application's `DATABASE_URL` secret is rotated to the clone's connection name.

---

## 7. Testing the Database Layer

Database-layer tests are planned for Phase J — see [PLAN.md](../PLAN.md). Coverage targets:

- View and stored-function output shape (`tests/test_db_views.py`)
- Trigger behaviour (duplicate-bookmark exception, `sources.updated_at` propagation)
- N+1 verification on `GET /articles/` (assert query count <= 5)
- TTL cleanup job (insert expired rows, run job, assert deleted count)

These tests will run against PostgreSQL in CI once Phase E (CI PostgreSQL service) lands.
