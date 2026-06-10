# Demo guide — aiFeelNews

On-screen reference for walking the data layer. Commands + what each one shows.
Companion to [DATABASE.md](DATABASE.md), [ER_Diagram.md](ER_Diagram.md), [db-queries.md](db-queries.md).

- **Local stack:** `docker-compose up -d` → web on host `:8002` (container internal :8080), db on `:5433`, then `docker-compose exec web python -m app.seeds.seed_db`
- **psql (local):** `docker-compose exec db psql -U postgres -d aifeelnews`
- **psql (live):** `cloud-sql-proxy aifeelnews:europe-west1:aifeelnews-db --port 5432 &` then `psql -h 127.0.0.1 -p 5432 -U aifeelnews -d aifeelnews`
- **Live API base:** `https://aifeelnews-web-813770885946.europe-west1.run.app`
- **Live frontend:** `https://aifeelnews-front.web.app/`

> `q` exits the psql pager (`(END)`). `\q` exits psql. `\pset pager off` at the start of a session avoids the pager entirely.

---

## 1. The schema

| Where | What it shows |
|---|---|
| `docs/ER_Diagram.md` (rendered Mermaid) | 10 tables, cardinalities, indexes. Two M2M: `bookmarks` (pure join), `article_entities` (join with payload — `salience`, `mention_count`). `ON DELETE CASCADE` on every child FK. |
| `\dt` | the 10 tables |
| `\d articles` | columns, indexes (`published_at` from initial migration; `sentiment_label`/`category`/`source_id` from `f2a3b4c5d6e7`), FKs, attached triggers |
| `\d bookmarks` | UNIQUE `(user_id, article_id)` **and** the duplicate-prevention trigger — both, on purpose |
| `\d article_entities` | M2M join: FKs to both sides + `salience`, `mention_count`, `analyzed_at`; UNIQUE `(article_id, entity_id)` |
| `\d crawl_jobs` | the `status` ENUM (PENDING/IN_PROGRESS/SUCCESS/FAILED/FORBIDDEN_BY_ROBOTS/RATE_LIMITED) — crawl modelled as a state machine row |

---

## 2. Views, functions, triggers

```
\dv                              -- 4 views: v_article_summary, v_source_stats, v_daily_sentiment, v_trending_entities
\df fn_*                         -- 2 stored functions: fn_sentiment_distribution, fn_source_performance
\df trg_fn_*                     -- the 2 trigger functions
SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE NOT tgisinternal;   -- the 2 table triggers
\sf fn_sentiment_distribution    -- function source (PL/pgSQL)
\sf trg_fn_prevent_duplicate_bookmark
\d+ v_trending_entities          -- view definition
```

All defined in migration `e1f2a3b4c5d6` (bookmark FK indexes + 4 views + 2 functions + 2 triggers).

### Views
```sql
SELECT * FROM v_article_summary   LIMIT 10;
SELECT * FROM v_source_stats      ORDER BY article_count DESC LIMIT 10;   -- per-source rollup: count, avg sentiment, date range
SELECT * FROM v_daily_sentiment   ORDER BY day DESC LIMIT 14;
SELECT * FROM v_trending_entities LIMIT 10;                                -- last-7-days window hardcoded in the view
```

### Stored functions (parameterized by a day window — same query, different window)
```sql
SELECT * FROM fn_sentiment_distribution(30);     -- sentiment label %, last 30 days
SELECT * FROM fn_sentiment_distribution(7);
SELECT * FROM fn_source_performance(30) LIMIT 10;   -- uses a LATERAL subquery for per-source entity richness
```

### Trigger — duplicate bookmark prevention
```sql
SELECT id FROM users    LIMIT 1;
SELECT id FROM articles LIMIT 1;

INSERT INTO bookmarks (user_id, article_id) VALUES (1, 1);   -- OK
INSERT INTO bookmarks (user_id, article_id) VALUES (1, 1);   -- raises: "Duplicate bookmark: user_id=1 already bookmarked article_id=1"

DELETE FROM bookmarks WHERE user_id = 1 AND article_id = 1;  -- cleanup, keeps the demo repeatable
```
Custom message comes from the trigger (a plain UNIQUE gives a generic constraint-name error). The UNIQUE is still there as defense-in-depth. App side: `app/routers/bookmarks.py:22-35` catches `IntegrityError` → `db.rollback()` → HTTP 409.

---

## 3. Indexing / query plans

```sql
EXPLAIN ANALYZE
SELECT id, title, sentiment_label, published_at
FROM articles
WHERE sentiment_label = 'positive'
ORDER BY published_at DESC
LIMIT 20;
-- look for: Index Scan / Bitmap Index Scan using ix_articles_sentiment_label  (was Seq Scan over ~30k rows before f2a3b4c5d6e7)
--           Buffers: shared hit=...   Execution Time: ... ms

EXPLAIN ANALYZE
SELECT a.id, a.title, s.name
FROM articles a JOIN sources s ON s.id = a.source_id
WHERE a.source_id = 1
ORDER BY a.published_at DESC
LIMIT 20;
-- ix_articles_source_id covers both the filter and the FK join
```

`articles.title ILIKE '%term%'` (the `/api/v1/articles/?search=` path) can't use a B-tree (leading wildcard) — so it's backed by a **`pg_trgm` GIN index** (`ix_articles_title_trgm`) that also drives `similarity()` ranking on Postgres. A separate **full-text** path on `/api/v1/articles/search` uses two generated `tsvector` columns (`search_vector` English, `search_vector_de` German) with GIN indexes, queried via `websearch_to_tsquery` + `ts_rank`. Both are live; see `DATABASE.md § 4.4`.

---

## 4. Cascade delete (don't actually delete seed data — wrap in a transaction if proving it)

```sql
-- what depends on article 1
SELECT 'content'          AS t, COUNT(*) FROM article_contents   WHERE article_id = 1
UNION ALL SELECT 'sentiment',       COUNT(*) FROM sentiment_analyses WHERE article_id = 1
UNION ALL SELECT 'crawl_jobs',      COUNT(*) FROM crawl_jobs        WHERE article_id = 1
UNION ALL SELECT 'article_entities',COUNT(*) FROM article_entities  WHERE article_id = 1
UNION ALL SELECT 'article_categories',COUNT(*) FROM article_categories WHERE article_id = 1;

BEGIN;
DELETE FROM articles WHERE id = 1;
SELECT COUNT(*) FROM article_contents WHERE article_id = 1;   -- 0 — cascaded
ROLLBACK;   -- nothing actually destroyed
```

---

## 5. Advanced SQL via the API (live)

Each endpoint maps to a function in `app/crud/analytics.py` (raw `text()` SQL). Open that file alongside.

```bash
curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/db-analytics/sentiment/rolling?days=14'
#   AVG() OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)  — 7-day rolling sentiment   [sentiment_rolling_average]

curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/db-analytics/sources/ranked?days=30'
#   RANK() OVER (ORDER BY avg_sentiment DESC), HAVING COUNT(*) >= n      — sources ranked            [source_sentiment_ranked]

curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/db-analytics/sentiment/breakdown?days=30'
#   GROUPING SETS — per-cell + row subtotal + col subtotal + grand total in one query                [sentiment_grouping_sets]

curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/db-analytics/entities/momentum?days=14'
#   two CTEs (adjacent windows) + FULL OUTER JOIN; CASE guards divide-by-zero for brand-new entities [entity_momentum]

curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/db-analytics/categories/daily?days=14'
#   SUM(...) OVER (PARTITION BY category ORDER BY day) — daily-per-category with cumulative totals     [daily_category_sentiment_pivot]

# Every db-analytics route takes an optional ?language= (EN/DE dashboard toggle):
curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/db-analytics/sentiment/breakdown?days=30&language=de'
#   same GROUPING SETS query, German articles only [sentiment_grouping_sets]
```

**Full-text search** (`app/crud/search.py`, `tsvector` + `ts_rank`):

```bash
# English FTS — phrases, OR, and leading - to exclude (websearch_to_tsquery):
curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/articles/search?q=climate%20change'

# German FTS — language=de filters to German AND uses the German stemming config
# (inflected forms match: "Wirtschaften" -> "Wirtschaft"):
curl 'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/articles/search?q=wirtschaft&language=de'
```

Same against local: swap the base URL for `http://localhost:8002`.

---

## 6. App-layer points (open in VSCode)

| File | Lines | What |
|---|---|---|
| `app/routers/articles.py` | 14–35 | eager-load strategy per relationship — `joinedload` for source / sentiment (1:1, low-N → JOIN), `subqueryload` for `article_entities` / `article_categories` (high-N → separate IN query, no Cartesian blowup). Without it: ~160 extra queries/request. |
| `app/schemas/source.py` | 31–41 | the second N+1 fix — `SourceRead` deliberately has **no** `articles` field; `from_attributes=True` made Pydantic v2 lazy-load it during serialization → route 504'd at 300s. Fix was removing the field, not tuning a loader. |
| `app/routers/bookmarks.py` | 22–35 | try insert → `except IntegrityError` → `db.rollback()` → 409. No pre-check SELECT (concurrent requests would race past it; the constraint is the real guard). |
| `app/jobs/crawl_worker.py` | 456–494 | per-article transactions; exception handler does `db.rollback()` **before** mutating the job to FAILED — a failed earlier commit leaves the session in `PendingRollbackError`, so order matters. |
| `app/database.py` | 32–33, 49–57 | `sessionmaker(autocommit=False, autoflush=False)`; `get_db()` yields a session per request, closed in `finally` (rolls back on unhandled exception). `pool_pre_ping` / `pool_recycle` = Cloud SQL idle-connection hygiene. |
| `app/crud/analytics.py` | — | the 5 advanced-SQL queries above, as raw `text()` SQL |
| `alembic/versions/e1f2a3b4c5d6_*.py` | — | the big migration: bookmark FK indexes + 4 views + 2 functions + 2 triggers |

```bash
docker-compose exec web alembic history --verbose     # linear chain, upgrade()/downgrade() each; runs on container start via docker/startup.sh
docker-compose exec web alembic current
docker-compose exec web pytest -v                     # current suite (SQLite fixture)
```

---

## 7. Infra / ops (live)

```bash
gcloud sql instances describe aifeelnews-db \
  --format='yaml(settings.backupConfiguration, settings.deletionProtectionEnabled)'
# expect: enabled: true, pointInTimeRecoveryEnabled: true, startTime: '03:00', deletionProtectionEnabled: true
```
Source of truth if offline: `infra/main.tf` (backup config, deletion protection, IAM bindings). Runtime DB user is the least-privileged `aifeelnews` (table DML only); migrations run in CI as the `postgres` superuser via the Cloud SQL Auth Proxy. `DATABASE_URL` is a Secret Manager `secretKeyRef`, not a plain env var.

`/metrics` (live): `https://aifeelnews-web-813770885946.europe-west1.run.app/metrics` — article/source counts, proof of real production data.

---

## What's worth showing against PRODUCTION vs the local seed

The local seed is ~50 articles, VADER-only, **no** `article_entities` / `article_categories` rows (VADER produces neither). So anything that needs volume, time-spread, GCP-NL output, or "real" numbers is more convincing live.

**Show against production (~35k articles, real time-spread, GCP NL data):**
- **Window-function analytics** — `sentiment/rolling`, `sources/ranked`, `entities/momentum`, `categories/daily`. A rolling average over 50 seed rows from one ingest is noise; over ~35k rows across real calendar time it actually *looks* like a trend. Momentum needs two adjacent populated windows — the seed barely has one.
- **`v_trending_entities`, `fn_source_performance`, anything touching entities/categories** — empty or trivial on the seed (no entity/category rows); meaningful in prod where GCP NL `annotateText` populated them.
- **`v_source_stats` / `v_daily_sentiment`** — 31 real sources with months of history vs. a handful of seed rows. The roll-up is the point; it needs rows to roll up.
- **`EXPLAIN ANALYZE` on the filtered article query** — the Seq-Scan-vs-Index-Scan difference is visible at ~35k rows; at 50 rows the planner may Seq Scan *anyway* (it's cheaper) and you can't show the win. Run this live for a real plan.
- **`/metrics`** — "34,xxx articles, 31 sources" is a one-line credibility anchor; the seed says "50".
- **Backup / PITR config** — `gcloud sql instances describe` only means anything against the real Cloud SQL instance.
- **`alembic current` on prod** — shows the prod DB is actually at `head`, migrations really run on deploy.

**Fine to show locally (deterministic, no network, doesn't depend on data volume):**
- **The duplicate-bookmark trigger** — insert/insert/error/cleanup. Behaviour, not data; identical local or live, and you control the rows.
- **`\dt` / `\dv` / `\df` / `\d <table>`** — schema introspection; the objects exist the same in both. (Though running `\dv`/`\df` against *prod* is a nice "and here they are on the live DB" beat.)
- **Cascade-delete demo** (`BEGIN; DELETE; ROLLBACK;`) — do this **locally**. Never run a DELETE against prod, even wrapped in a transaction.
- **The code walk** (articles.py / bookmarks.py / analytics.py / the migration) — it's source, environment-irrelevant.
- **`pytest`** — runs on the SQLite fixture regardless; show it locally.

Rule of thumb: **behaviour and structure → local** (controlled, repeatable, safe). **Numbers, trends, plans, ops config → production** (real, and the seed can't fake it). Never write to prod.
