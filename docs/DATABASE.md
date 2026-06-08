# Database — aiFeelNews

PostgreSQL 14, accessed through SQLAlchemy 2.0 (`Mapped[]` typed ORM) and managed with Alembic. Ten tables, two many-to-many relationships (`bookmarks` and `article_entities`), and a layer of database objects — views, stored functions, and triggers — that push aggregation logic into the database where it belongs.

This doc covers the operational concerns: setup, migrations, schema objects, optimization patterns, and the data lifecycle. The full schema (table-by-table column listing, cardinality, index map) lives in [ER_Diagram.md](ER_Diagram.md).

---

## 1. Local Setup

The supported local path is **Docker Compose**. The migration chain uses PostgreSQL-only DDL (`CREATE OR REPLACE VIEW`, PL/pgSQL functions, `::numeric` casts), so a bare-SQLite path can't run `alembic upgrade head` end-to-end — SQLite is used by the test suite only, via `Base.metadata.create_all`.

### Quick start (Docker)

**Prereqs:** Docker Desktop / Docker Engine + Compose.

```bash
# 1. Copy the example env file. The committed defaults are sufficient for
#    local Compose; Mediastack/Firebase keys are only needed for live
#    ingestion and bookmark/auth flows respectively.
cp .env.example .env

# 2. Bring up the full stack (Postgres 14, FastAPI web, worker, scheduler).
#    First boot builds the images (~2-3 min); subsequent boots are seconds.
docker-compose up --build

# 3. Seed the database with the bundled 50-article snapshot so the UI has
#    something to render. Run this in a second terminal once `web` is up.
docker-compose exec web python -m app.seeds.seed_db

# 4. (Optional) Exercise the full ingestion pipeline. Adds PENDING crawl
#    jobs for every seeded article; the worker picks them up and crawls
#    the live article URLs (robots.txt-respecting, rate-limited).
docker-compose exec web python -m app.seeds.seed_db --queue-crawl-jobs
docker-compose logs -f worker

# 5. (Optional) run the test suite inside the web container.
docker-compose exec web pytest -v
```

The API is then served at `http://localhost:8002` on the host — the container itself runs on `:8080` internally, but docker-compose publishes it on host port `:8002` to avoid the local Apache/XAMPP that commonly squats on `:8080` on Windows dev boxes (e.g. `GET /articles/?limit=5`). The frontend in `frontend/` is run separately with `npm run dev` — see [README.md § Development Setup](../README.md#development-setup).

### What's running

| Service | Image | Purpose |
|---------|-------|---------|
| `db` | `postgres:14` | Database; persists in a Docker volume |
| `web` | `aifeelnews-web` | FastAPI app; runs migrations on start |
| `worker` | `aifeelnews-worker` | Background crawler — fetches article body content for jobs in the `crawl_jobs` queue |
| `scheduler` | `aifeelnews-scheduler` | Hourly Mediastack ingestion loop (when `MEDIASTACK_API_KEY` is set) |

### Running without Docker

The bare-metal path (Postgres on the host, `uvicorn` on the host) works the same way as inside the container — install dependencies, point `LOCAL_DATABASE_URL` at a Postgres 14 instance, run `alembic upgrade head`, then `python -m app.seeds.seed_db`. SQLite is **not** a supported substitute for Postgres at the migration layer.

---

## 2. Migrations

Fourteen migrations, applied in order. Run `alembic upgrade head` to apply, `alembic downgrade -1` to roll back the most recent one.

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
| 10 | `f2a3b4c5d6e7` | Article filter indexes — `sentiment_label`, `category`, `source_id` |
| 11 | `a1b2c3d4e5f6` | Fix ambiguous column in `fn_sentiment_distribution` |
| 12 | `54bff216cdb7` | Drop `NOT NULL` on `users.hashed_password` |
| 13 | `2d60fa48c9ba` | Reconcile `sources` schema with model (unique index, comments) |
| 14 | `7c3e9a4f1b82` | Add denormalized `articles.sentiment_magnitude` (GCP NL) |

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

### 4.1 N+1 Query Fixes

Two distinct N+1 patterns have shipped fixes. They look similar in a profiler — too many queries per request — but originate at different layers and call for different remedies.

#### `GET /articles/` — choose the right eager-load strategy

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

#### `GET /sources/` — don't declare unbounded relationships in the response schema

`SourceRead` originally declared `articles: Optional[List[ArticleRead]] = None` with `from_attributes=True`. Pydantic v2 accesses SQLAlchemy relationship attributes during response serialisation even when the field default is `None` — so every `/sources/` call lazy-loaded `Source.articles`, and each Article then fanned out into its own lazy chain (`bookmarks`, `crawl_jobs`, `content`, `sentiment_analyses`, `article_entities`, `article_categories`). Tolerable when sources held ~50 articles each; at production scale (22 sources × ~1,300 articles each) the route 504'd at the 300s Cloud Run timeout.

The fix removes the `articles` field from `SourceRead` ([app/schemas/source.py](../app/schemas/source.py)). The SQLAlchemy relationship stays on the model — only the response schema changes. No consumer was reading the nested array. If a future endpoint genuinely needs the nested shape, define a separate `SourceWithArticlesRead` and load it via `selectinload` so the relationship is bounded.

The contrast matters: the first fix is about *strategy choice once a relationship is being accessed*; the second is about *not declaring an unbounded relationship in the response shape in the first place*. The first lives in the route, the second lives in the schema.

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

### 4.4 Article Filter Indexes

The `/articles/` endpoint accepts `sentiment_label`, `category`, `source_id`, and `search` query parameters. Without indexes, every filtered request was a sequential scan over ~30k rows. Added in [migration f2a3b4c5d6e7](../alembic/versions/f2a3b4c5d6e7_add_article_filter_indexes.py):

```sql
CREATE INDEX ix_articles_sentiment_label ON articles (sentiment_label);
CREATE INDEX ix_articles_category        ON articles (category);
CREATE INDEX ix_articles_source_id       ON articles (source_id);
```

PostgreSQL's planner combines an index lookup on the filter column with the existing `(published_at, id)` order to serve the page directly from the index, instead of scanning then sorting. The `source_id` index also covers the FK join used by the eager-load on `Article.source` ([app/routers/articles.py:30-35](../app/routers/articles.py#L30-L35)).

**Search is intentionally unindexed.** The `search` parameter does `WHERE title ILIKE '%term%'`, which a B-tree cannot accelerate — the leading `%` defeats prefix matching. The production-grade upgrade path is PostgreSQL's `pg_trgm` extension with a GIN index:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_articles_title_trgm ON articles USING gin (title gin_trgm_ops);
```

This is deferred because the SQLite test fixture used by the pytest suite cannot exercise `pg_trgm` — it would require a Postgres CI service (tracked in PLAN.md as Phase E). At ~30k articles a sequential scan on `title` returns in tens of milliseconds, so the upgrade is a forward-looking optimization, not a current bottleneck.

### 4.5 Index Inventory

Composite and performance indexes are listed in [ER_Diagram.md § Composite & Performance Indexes](ER_Diagram.md#composite--performance-indexes). Highlights: `entities (name, type)` UNIQUE for canonical deduplication, `article_entities (article_id, entity_id)` UNIQUE preventing duplicate mentions, `article_contents (expires_at)` for the TTL cleanup job, and the article filter indexes documented above.

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

## 7. Data

Production runs an active ingestion pipeline that pulls article metadata from Mediastack every 8 hours via Cloud Scheduler. As of 2026-05-03 the production database holds **29,812 articles across 22 sources**, with sentiment + entity + category annotations attached by the crawl worker. Article bodies are truncated to 1024 characters and expire after 7 days; metadata (title, URL, sentiment score, entities, categories) is retained indefinitely.

For local development a static seed dataset is included at [`app/seeds/seed_data.json`](../app/seeds/seed_data.json) — **50 articles spanning 10 sources** (BBC, Reuters/Independent, Guardian, NYTimes, Bloomberg, CNBC, FinancialPost, Phys, DW, Google News), sampled from the production database with PII removed (no `users`, no `bookmarks`). Load it with:

```bash
alembic upgrade head
python -m app.seeds.seed_db        # idempotent — re-runs skip URLs already present
python -m app.seeds.seed_db --reset  # wipe seed-derived rows first, then re-insert
```

The seed loader is documented in [app/seeds/seed_db.py](../app/seeds/seed_db.py); the export tool that generated the JSON (against the live Cloud SQL Auth Proxy) is intentionally gitignored as one-off local tooling.

---

## 8. Testing the Database Layer

Database-layer tests are planned for Phase J — see [PLAN.md](../PLAN.md). Coverage targets:

- View and stored-function output shape (`tests/test_db_views.py`)
- Trigger behaviour (duplicate-bookmark exception, `sources.updated_at` propagation)
- N+1 verification on `GET /articles/` (assert query count <= 5)
- TTL cleanup job (insert expired rows, run job, assert deleted count)

These tests will run against PostgreSQL in CI once Phase E (CI PostgreSQL service) lands.
