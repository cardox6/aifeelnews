# aiFeelNews — Capstone Project Discussion

Matias Cardone · matias.cardone@code.berlin · Spring Semester 2026

Module: Capstone Project · Project: aiFeelNews · Specialty: Web Backend

CODE University of Applied Sciences, Berlin · Supervisor: Frank Trollmann · 10 June 2026 · Live: [aifeelnews-front.web.app](https://aifeelnews-front.web.app)

This is my discussion of aiFeelNews against the assessment areas agreed in my
capstone registration: architecture and technology choices, source code quality,
technical documentation, the Web Backend specialty, and my part in shaping
requirements and preparing the evaluation. It starts with the system as a whole,
spends most of its time on the backend (§3), and closes with the trade-offs I
knowingly carry. Where I claim something about the code, I anchor it to a file and
line range so it can be checked in the repository rather than taken on faith.

aiFeelNews is a full-stack, cloud-native system: a backend API, a relational
database, an ingestion pipeline, an analytics layer, and a Svelte frontend,
deployed on Google Cloud. Three university modules — Cloud Computing, Relational
Databases, and Cybersecurity — already assessed parts of it (§4.4). The part
written for this submission is §3: the case that the backend is built the way a
backend should be, with regard to scalability and maintainability.

---

## 1. What I built

The system ingests news articles from the Mediastack API on a schedule, fetches
the original article body with a custom crawler (respecting `robots.txt`,
truncating to 1,024 characters, expiring content after 7 days), scores sentiment
with Google Cloud Natural Language — entities and topic categories included — with
a VADER fallback, and persists everything to PostgreSQL. A FastAPI backend exposes
the data through a versioned REST API, consumed by a Svelte 5 single-page app: a
filterable, bilingual-searchable article feed with sentiment context, per-user
bookmarks, and an analytics dashboard of aggregated insights per outlet and per
entity. It runs on Google Cloud Run as three containers (web, worker, scheduler)
against Cloud SQL, with BigQuery as an OLAP sidecar and Firebase for
authentication and hosting. The point, per my exposé: help readers notice how news
is written, not just what it reports.

### 1.1 What the exposé promised, and what shipped

My registration ties the specialty to the application being "online and functional
according to the goals of the exposé", so here is that mapping, commitment by
commitment:

| What I committed to | Status | Where |
|---|---|---|
| Articles enriched with sentiment scores and explanatory context | Delivered | Feed with sentiment label, score, and magnitude per article; interpretation context in the UI ([`frontend/src/lib/ArticleCard.svelte`](../../frontend/src/lib/ArticleCard.svelte), [`frontend/src/lib/sentiment.ts`](../../frontend/src/lib/sentiment.ts)) |
| Bookmarking for later review | Delivered | Per-user bookmarks behind Firebase auth ([`app/routers/bookmarks.py`](../../app/routers/bookmarks.py)) |
| Filtering by news outlet | Delivered, plus extras | Outlet filter plus sentiment and category filters, and bilingual (EN/DE) full-text search beyond the exposé scope ([`app/routers/articles.py`](../../app/routers/articles.py)) |
| Aggregated sentiment metrics per outlet | Delivered | Source ranking, mood-over-time, and sentiment-by-category dashboard charts ([`app/routers/db_analytics.py`](../../app/routers/db_analytics.py)) |
| Aggregated metrics per entity (feasibility-caveated in the exposé) | Delivered | Trending-names momentum chart (Postgres) and Top-Entities chart (BigQuery), both behind a data-quality gate (§3.3). No dedicated entity-browser page yet — the API exists ([`app/routers/entities.py`](../../app/routers/entities.py)); see §5 |
| Deployed, demonstrable cloud prototype | Delivered | Live at [aifeelnews-front.web.app](https://aifeelnews-front.web.app) (frontend on Firebase Hosting, API on Cloud Run); reproducible local demo via `make demo`, no credentials needed (§3.2) |
| SvelteKit migration (exposé roadmap, Phase 4) | Dropped, by decision | A design-token restyle on plain Svelte delivered the same UX goals at a fraction of the migration's cost and risk. Reasoning in §5 |

---

## 2. Architecture and technology decisions

### 2.1 The stack, and why

I picked every part of this stack for a reason I can defend. The common thread is
a system that one person can build, operate, and afford.

The backend is FastAPI on Python 3.14. I wanted request and response models
validated at the framework boundary (Pydantic), OpenAPI documentation generated
rather than hand-maintained, and an async path available for the day the workload
justifies it (§3.1 explains why it doesn't yet). Python also keeps the NLP
ecosystem — VADER, the Google Cloud client libraries — first-class.

Data lives in PostgreSQL 14, accessed through SQLAlchemy 2.0 with Alembic
migrations. The domain is plainly relational: articles belong to sources, entities
and categories attach many-to-many, bookmarks are per-user, and the analytics
aggregate over time windows. Postgres also carries work that would otherwise leak
into application code: the window functions and `GROUPING SETS` behind the
analytics, generated `tsvector` columns for bilingual full-text search, and the
views, functions, and triggers discussed in §3.3. Typed `Mapped[]` models keep the
schema and the code in one type system.

The frontend is a Svelte 5 + TypeScript SPA on Firebase Hosting. Compile-time
reactivity and a small bundle felt proportionate to a data-driven prototype; I did
not need a virtual DOM, or a meta-framework, to render a feed and a dashboard.

The platform is Google Cloud, managed services throughout. Cloud Run scales to
zero, and a news-analysis tool has exactly the traffic shape that rewards it:
bursty, low baseline, tolerant of a cold start. The Natural Language API returns
sentiment, entities, and classification in a single `annotateText` call — one call
instead of three cut that cost by 66%
([README, "Key Design Decisions"](../../README.md#key-design-decisions)). Cloud
Scheduler triggers ingestion over OIDC, BigQuery takes the OLAP load, and Secret
Manager holds the six production secrets. This buys real leverage and real vendor
lock-in; I accept that trade and say so in §5.

Everything ships as three slim, non-root Docker images, and the entire platform —
Cloud SQL, IAM, Secret Manager, Scheduler, BigQuery, monitoring, 35+ resources —
is declared in Terraform ([`infra/main.tf`](../../infra/main.tf)). An environment
is something I can review and reproduce, not something I clicked together
([`docs/MULTI_ENVIRONMENT_STRATEGY.md`](../MULTI_ENVIRONMENT_STRATEGY.md)).

### 2.2 How the pieces fit

I split the system into three containers with one job each: a stateless `web`
API, a `worker` that crawls and analyzes, and a `scheduler` that triggers
ingestion. The user-facing tier never blocks on pipeline work, and each part
scales — or stops — on its own. Two more boundaries shape the design. Operational
reads and writes go to Cloud SQL, while long-range aggregation streams to
BigQuery, feature-gated so the core application has no hard dependency on the
analytics stack. And people and machines authenticate differently: Firebase ID
tokens for users, Google-signed OIDC for the scheduler calling the service. The
ingestion pipeline is built around cost discipline end to end — a free VADER score
at ingest, exactly one metered `annotateText` call per article with a guard
against re-analysis, and a newest-first processing budget sized to the API free
tier (§3.1). Diagrams in
[`docs/Cloud_Architecture_Diagram.drawio.png`](../Cloud_Architecture_Diagram.drawio.png);
the service-to-code mapping is in
[`docs/CLOUD_SERVICE_CODE_MAP.md`](../CLOUD_SERVICE_CODE_MAP.md).

### 2.3 How data is persisted

The schema is ten normalized models with many-to-many article↔entity and
article↔category links, denormalized on purpose along the hot read path (sentiment
label, score, and magnitude are mirrored onto `articles`, §3.1). Seventeen Alembic
migrations are the single source of schema truth — including the Postgres-only DDL
for views, PL/pgSQL functions, and triggers — and they run in CI before every
deploy (§3.2). The full schema discussion is in [`docs/DATABASE.md`](../DATABASE.md)
and [`docs/ER_Diagram.md`](../ER_Diagram.md).

### 2.4 Security

I developed the security posture inside the Cybersecurity module (§4.4), where it
was separately assessed: a STRIDE threat model
([`docs/THREAT_MODEL.md`](../THREAT_MODEL.md)) and a catalogue of 38 implemented
controls across 8 layers ([`docs/SECURITY_MEASURES.md`](../SECURITY_MEASURES.md)) —
identity (Firebase plus custom-claims RBAC, §3.4), secrets (Secret Manager,
gitleaks), transport (HTTPS-only, SSL-enforced Cloud SQL, a CORS allowlist),
application (Pydantic validation, parameterized queries only, rate limiting), data
protection (the 1,024-character truncation and 7-day TTL), containers (non-root
users), supply chain (Dependabot, `pip-audit`, gitleaks in CI), and monitoring.

---
## 3. The specialty: web backend

The registration ties the specialty to scalability and maintainability. Both
sections below are written the same way: what I did, why, and where to check it.

### 3.1 Scalability

The web tier itself scales trivially. It is stateless and deploys with
`--min-instances=0 --max-instances=10 --concurrency=80`
([`.github/workflows/deploy.yml:216-218`](../../.github/workflows/deploy.yml#L216-L218)),
so it costs nothing idle and fans out under load
([`docs/COST_AND_SCALABILITY.md` §3](../COST_AND_SCALABILITY.md)). The part that
required actual thought is the database connection budget. Cloud SQL caps
`max_connections` at 50 ([`infra/main.tf:88`](../../infra/main.tf#L88)), and the
instinct under load is to grow the connection pool — here the correct move was to
shrink it. I sized the pool at `pool_size=2, max_overflow=2`
([`app/database.py:54-56`](../../app/database.py#L54-L56)): four connections per
instance, forty at full scale-out, safely under the cap. SQLAlchemy's default of
fifteen per instance would have over-subscribed the limit three times over. The
pool is also built to survive its environment — `pool_pre_ping` for Cloud SQL
failovers, hourly recycling, and a fail-fast ten-second timeout instead of the
silent thirty-second default
([`app/database.py:52-56`](../../app/database.py#L52-L56)). Past roughly twelve
instances, PgBouncer is the documented next step
([`docs/COST_AND_SCALABILITY.md`, "Connection Pool Sizing"](../COST_AND_SCALABILITY.md)).

For the same reason, I kept the request handlers synchronous. They run in
Starlette's thread pool, and the connection pool saturates before the thread pool
does — an async rewrite (`asyncpg`, `AsyncSession`) would move complexity around
without moving the bottleneck. Instead of migrating by reflex, I wrote down the
reasoning and the conditions under which I would change my mind
([`docs/COST_AND_SCALABILITY.md`, "Request Concurrency Model"](../COST_AND_SCALABILITY.md)).

The read path is tuned where it is actually hot. The three filter columns each
have a B-tree index
([`alembic/versions/f2a3b4c5d6e7_add_article_filter_indexes.py:23-25`](../../alembic/versions/f2a3b4c5d6e7_add_article_filter_indexes.py#L23-L25)),
and the article list orders by `(published_at desc, id desc)` — a total ordering
with a unique tie-breaker
([`app/routers/articles.py:65-67`](../../app/routers/articles.py#L65-L67)), which
makes the eventual move from OFFSET/LIMIT to keyset pagination a drop-in (§5). The
list endpoint eager-loads exactly what the serializer reads — `joinedload` for the
source, `subqueryload` for entities and categories — and nothing else; I removed
the `sentiment_analyses` eager-load once the response switched to the denormalized
columns ([`app/routers/articles.py:44-48`](../../app/routers/articles.py#L44-L48)),
which avoids N+1 queries without loading data only to discard it. The same
denormalization carries `sentiment_magnitude` onto the article
([`app/models/article.py:43`](../../app/models/article.py#L43), written by the
worker at [`app/jobs/crawl_worker.py:415`](../../app/jobs/crawl_worker.py#L415)),
so serving the feed never touches the analysis relationship. The heavy routes sit
behind one shared `slowapi` limiter
([`app/deps/ratelimit.py:11`](../../app/deps/ratelimit.py#L11)) — 30/min
analytics, 60/min sentiment, 6/h scheduler, 60/min metrics, all overridable by
environment variable
([`app/config/security.py:42-45`](../../app/config/security.py#L42-L45)),
including every advanced-SQL `db-analytics` route
([`app/routers/db_analytics.py:42,55,67,79,91`](../../app/routers/db_analytics.py#L42)).
And long-range aggregation is off the operational path entirely: streamed to
BigQuery behind an `ENABLE_BIGQUERY` flag
([`app/routers/analytics.py`](../../app/routers/analytics.py)), while the
dashboard can serve the same shapes straight from Postgres so a demo never
depends on the analytics stack
([`app/routers/db_analytics.py`](../../app/routers/db_analytics.py)).

The ingestion pipeline scales by discipline rather than horsepower. The crawl →
NLP stage lives inside the Cloud NL free tier (roughly 4,500 calls a month), so it
cannot process everything at once. I made job creation and job processing both run
newest-first
([`app/jobs/crawl_worker.py:529,555`](../../app/jobs/crawl_worker.py#L529)) under
a per-run budget knob (`max_crawl_job_creation`,
[`app/config/scheduler.py:36`](../../app/config/scheduler.py#L36)): fresh articles
get analyzed first and the backlog drains from the top, instead of new content
starving behind old. The spend itself is guarded. Ingestion stores a free VADER
provisional score
([`app/jobs/normalize_articles.py`](../../app/jobs/normalize_articles.py)), the
worker makes the single authoritative `annotateText` call, and a re-analysis guard
makes retries cost nothing
([`app/jobs/crawl_worker.py`](../../app/jobs/crawl_worker.py)). That guard exists
because I caught the worker re-analyzing articles it had already analyzed — about
6.6× the necessary spend — while re-checking pipeline costs, and closed the hole.

### 3.2 Maintainability

By maintainability I mean that someone who is not me — or me, six months from now
— can understand, change, and deploy this system safely.

The code is layered routers → CRUD/services → models, with database sessions and
auth injected as dependencies
([`docs/PROJECT_STRUCTURE.md`](../PROJECT_STRUCTURE.md)). Configuration is one
Pydantic `BaseSettings` module per concern (database, ingestion, sentiment,
security, …), and anything operational is an environment variable with a sensible
default ([`app/config/security.py:42-45`](../../app/config/security.py#L42-L45)).
Types run end to end — SQLAlchemy 2.0 `Mapped[]` models
([`app/database.py:11`](../../app/database.py#L11),
[`app/models/article.py:22-42`](../../app/models/article.py#L22-L42)), Pydantic v2
response models — and mypy runs in CI
([`.github/workflows/deploy.yml:81`](../../.github/workflows/deploy.yml#L81)), so
a typing regression blocks the merge instead of surprising someone later.

Deploys are built to be boring. `alembic upgrade head` runs against production
before each Cloud Run rollout — as the superuser for that step only, while the
runtime app connects as the least-privileged `aifeelnews` role
([`.github/workflows/deploy.yml:178-184`](../../.github/workflows/deploy.yml#L178-L184))
— and the same views, functions, and triggers are exercised against a real
Postgres service container in the test job
([`.github/workflows/deploy.yml:37-49`](../../.github/workflows/deploy.yml#L37-L49)).
After rollout, the pipeline verifies `/health`, the revision identity, `/metrics`,
and a live API read, and shifts traffic back to the previous revision if anything
fails ([`.github/workflows/deploy.yml:221-300`](../../.github/workflows/deploy.yml#L221-L300)).
Errors are handled once, centrally: a global exception handler returns a generic
500 and logs the cause server-side
([`app/main.py:102-114`](../../app/main.py#L102-L114)), the probes keep their 503
semantics, and a failed login returns a deliberately uninformative `Invalid token`
401 ([`app/deps/auth.py:26-31`](../../app/deps/auth.py#L26-L31)).

Environments are code. The platform is ~889 lines of Terraform — Cloud SQL, IAM,
Secret Manager, Scheduler, BigQuery, monitoring — with separate prod and staging
tfvars ([`docs/MULTI_ENVIRONMENT_STRATEGY.md`](../MULTI_ENVIRONMENT_STRATEGY.md)),
and every frontend-touching PR gets an isolated, auto-expiring Firebase Hosting
preview
([`firebase-hosting-pull-request.yml`](../../.github/workflows/firebase-hosting-pull-request.yml)).
I also built Cloud Run previews per PR for the backend — and then removed them on
purpose. A preview revision needs a database, and neither pointing unreviewed code
at production data nor paying for a second always-on Cloud SQL instance was
acceptable, so I deleted the jobs rather than leave them half-working and recorded
the decision
([`docs/MULTI_ENVIRONMENT_STRATEGY.md`, "Cloud Run PR Previews (Removed by Design)"](../MULTI_ENVIRONMENT_STRATEGY.md#cloud-run-pr-previews-removed-by-design)).

A reviewer can also hold the system in their hands without any credentials:
`make demo` brings up the full stack on a reproducible dataset — no API keys, no
GCP project. Two decisions make it deterministic. The worker and scheduler sit
behind a `pipeline` Docker Compose profile
([`docker-compose.yml`](../../docker-compose.yml)), so a default bring-up never
pulls live Mediastack data over the seed; and the seed itself is a fully enriched,
date-anchored production sample (sentiment, magnitude, entities, categories) that
the loader re-anchors to "now", so every analytics chart populates offline. The
seeder's enrichment and its date-offset invariant are covered by tests
([`tests/test_seed_db.py`](../../tests/test_seed_db.py)). The public read API —
the feed and the full dashboard — needs no login; only per-user bookmarks require
a Firebase token.

Finally, both halves of the stack gate every PR. The backend pytest suite runs on
SQLite for speed with a real Postgres service container for the SQL-specific
paths, and the frontend has its own Vitest + Testing Library suite: the `api.ts`
contract (query-string assembly, status-code semantics, Postgres `Decimal`-string
coercion), sentiment interpretation, the bookmark store, theme persistence, and
component rendering
([`frontend/src/lib/*.test.ts`](../../frontend/src/lib/api.test.ts)), run in CI
next to `svelte-check` and `tsc`
([`.github/workflows/frontend-check.yml`](../../.github/workflows/frontend-check.yml)).
A behavioral regression in the SPA now fails the PR, even though `vite build` —
which strips types without checking them — would happily pass.

### 3.3 The database does real work

The analytics layer is PostgreSQL doing what it is good at, not application-side
loops: window functions, CTEs with `RANK()`, `GROUPING SETS`, and a
`FULL OUTER JOIN` momentum query, all in
[`app/crud/analytics.py`](../../app/crud/analytics.py)
([rolling average `:41-44`](../../app/crud/analytics.py#L41-L44),
[RANK + CTE `:63,81`](../../app/crud/analytics.py#L63),
[GROUPING SETS `:147-152`](../../app/crud/analytics.py#L147-L152),
[FULL OUTER JOIN `:237-238`](../../app/crud/analytics.py#L237-L238)), exposed as
rate-limited endpoints and wired into the dashboard.

Data quality is enforced inside the query, not cleaned up after it. The first
version of the top-entities chart was dominated by Getty Images, Reuters, and the
BBC — real organizations, but publishers and image credits, not what the news was
about. The fix is a two-layer gate: Knowledge-Graph resolution
(`wikipedia_url IS NOT NULL`, which drops generic common nouns) plus a curated
publisher denylist. It lives in one place
([`app/constants/entity_filters.py`](../../app/constants/entity_filters.py)) and
applies identically to the Postgres momentum query and the three BigQuery entity
queries — parameterized in both dialects, expanding binds in Postgres and
`NOT IN UNNEST(@param)` in BigQuery, never string interpolation. The denylist is
bilingual because the German feed surfaced its own publisher self-references
(Focus, Spiegel, ARD, dpa, …) when I inspected the live German ranking; the gate
grew as the data revealed new pollution. Full rationale in
[`docs/DATABASE.md` § 4.3a](../DATABASE.md#43a-entity-quality-gate).

Search is bilingual in the only way Postgres lets it be correct. A generated
column's expression must be immutable, and `to_tsvector` with a per-row config is
not — so one column cannot stem both languages. The FTS endpoint is therefore
backed by two generated `tsvector` columns, `search_vector` (`english`) and
`search_vector_de` (`german`), each GIN-indexed (migrations `b4e2d5c6f7a8` and
`c5f3a6b7d8e9`); a `language=de` query targets the German column so inflected
forms stem correctly. The analytics queries take an optional `language` filter
that only joins when set, which leaves the all-languages query plan untouched
([`app/crud/analytics.py:27-34`](../../app/crud/analytics.py#L27-L34)).

### 3.4 Access control

Authorization composes three things: ownership checks on bookmarks,
deny-by-default everywhere, and role-based access via Firebase custom claims. I
put the `role` claim inside the Google-signed ID token rather than in a database
column — it is read server-side
([`app/deps/auth.py:38,76`](../../app/deps/auth.py#L38)), and `require_admin`
([`app/deps/auth.py:80-92`](../../app/deps/auth.py#L80-L92)) gates
`POST /api/v1/sources/`
([`app/routers/sources.py:20`](../../app/routers/sources.py#L20)). No role column,
no email allowlist, no second source of truth: the role is verified by Google's
signature on every request. The full model is in
[`docs/SECURITY_MEASURES.md` §1.7](../SECURITY_MEASURES.md).

---
## 4. The remaining assessment areas

### 4.1 Source code quality

The structural side is covered above: layered modules, per-concern configuration,
end-to-end typing with mypy and Ruff as CI gates, and a test suite on both halves
of the stack — backend pytest with a real-Postgres job for the SQL-heavy paths,
frontend Vitest for the logic layer (§3.2).

As for algorithms and data structures: the interesting ones in this system live in
the database, by design. Aggregation is set-based SQL — window functions,
`GROUPING SETS` — instead of Python loops over result sets; search runs on
GIN-indexed `tsvector` columns instead of `LIKE` scans; the filter columns carry
B-tree indexes matched to the queries that actually run; and the crawl queue is a
priority queue expressed as an `ORDER BY` plus a budget (§3.1). Where the
application layer is the right place — the hot list endpoint — it avoids N+1 with
targeted eager-loading and denormalized read columns rather than ORM defaults.

### 4.2 Technical documentation

The [README](../../README.md) gets a developer from clone to running system: setup
for Docker and bare-metal, the credential-free demo path, run modes, the API
surface, and the key design decisions. The `docs/` tree carries the deeper
material:

| Document | Purpose |
|---|---|
| [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) | Module layout + responsibilities |
| [COST_AND_SCALABILITY.md](../COST_AND_SCALABILITY.md) | Cost reasoning, pool sizing, concurrency model, scaling tiers |
| [SECURITY_MEASURES.md](../SECURITY_MEASURES.md) | Layered security controls catalogue |
| [THREAT_MODEL.md](../THREAT_MODEL.md) | STRIDE threat model |
| [DATABASE.md](../DATABASE.md) | Schema, views, functions, triggers, indexing |
| [ER_Diagram.md](../ER_Diagram.md) | Entity-relationship model |
| [CICD_PIPELINE.md](../CICD_PIPELINE.md) | Build / test / deploy / rollback pipeline |
| [MULTI_ENVIRONMENT_STRATEGY.md](../MULTI_ENVIRONMENT_STRATEGY.md) | prod/staging via Terraform tfvars; preview strategy |
| [CLOUD_SERVICE_CODE_MAP.md](../CLOUD_SERVICE_CODE_MAP.md) | GCP service → code mapping |
| [PERSONAS_AND_USE_CASES.md](../PERSONAS_AND_USE_CASES.md) | Personas, use cases, traceability |

The development process behind it: simplified Git Flow (feature → develop → main)
with a CI-enforced merge policy, PR-based review, migrations as code, pre-commit
hooks (ruff, mypy, gitleaks), and Dependabot, `pip-audit`, and CodeQL watching the
supply chain ([`docs/CICD_PIPELINE.md`](../CICD_PIPELINE.md)).

### 4.3 Requirements and evaluation

The registration calls this area "Apply Interactively": did I distill the
requirements, and did I prepare the evaluation from a technical point of view.

I broke the exposé's media-literacy goal down into four personas and 27 use cases
with a use-case → schema traceability matrix
([`docs/PERSONAS_AND_USE_CASES.md`](../PERSONAS_AND_USE_CASES.md)), so every table
in the database exists for a requirement I can name — and §1.1 maps each exposé
commitment to what shipped. Some requirements only emerged from the running
system, and I treated those as requirements too: the entity-quality gate exists
because the live chart was full of publishers instead of subjects (§3.3), the
bilingual search columns exist because German articles made single-config
stemming visibly wrong, and the Compose `pipeline` profile exists because the
demo dataset kept drifting under a background scheduler (§3.2).

For the evaluation itself, I prepared three levels of access: the live deployment
with its health, version, and metrics endpoints; the `make demo` path that
reproduces the system with zero credentials; and documents whose claims are
checkable — this discussion is anchored to files and lines, and the module
submissions include literal `curl` transcripts (observed 401s, the 429 rate-limit
kick-in, the CORS rejection) and runnable SQL. The self-reflection essay carries
the self-assessment itself.

### 4.4 What the three modules already assessed

This system grew through three module assessments before the capstone: **Cloud
Computing** (passed) — infrastructure as code, containerization, CI/CD, cost and
multi-environment reasoning; **Relational Databases** (passed) — schema design,
views, functions and triggers, advanced SQL, ORM usage; and **Cybersecurity**
(passed, defended in the May 2026 oral) — the STRIDE threat model and the layered
controls summarized in §2.4. The Cybersecurity and Relational-Databases
submission documents sit next to this one in [`docs/submissions/`](.). The
capstone builds on that assessed base; the backend case in §3 is what is new
here.

---

## 5. Trade-offs I accept, for now

Each of these is a deliberate decision at the current scale, and each has its
next step documented.

- **Pagination is OFFSET/LIMIT, not keyset.** Fine at this scale; deep offsets get
  slow eventually. The `(published_at, id)` ordering is already total (§3.1), so
  keyset is a drop-in when needed — together with a composite index backing the
  ORDER BY, which I would add in the same change.
- **Handlers are synchronous.** Correct while the connection pool is the binding
  constraint; the async path (`asyncpg`, `AsyncSession`) is documented for the day
  per-instance request rate justifies it (§3.1).
- **Most backend tests run on SQLite; only the SQL-specific ones use real
  Postgres.** A speed-vs-fidelity trade I keep narrowing, not closing. On the
  frontend, the logic layer is tested while the two large view components
  (Dashboard, ArticleCard) are not. Presentation-heavy tests tend to break on
  cosmetic changes rather than catch real bugs, and the logic those components
  render is covered (§3.2).
- **No SvelteKit migration.** The exposé's Phase 4 planned one. What the migration
  was *for* — a coherent, navigable, themed UX — was delivered by a design-token
  restyle and a lightweight view state machine on plain Svelte, at a fraction of
  the cost and regression risk. Routing-dependent features (an article detail
  page, deep links) stay on the roadmap and are what would justify SvelteKit when
  they land. I would rather record a changed decision than quietly drop a promise.
- **No entity-browser page.** The API exists
  ([`app/routers/entities.py`](../../app/routers/entities.py)) and the dashboard
  charts consume the same gated data; a browsable entity page is roadmap, not
  rework.
- **Vendor lock-in is real, and accepted.** Cloud Run, Cloud SQL, the Natural
  Language API, BigQuery, and Firebase are all Google-managed. The containers are
  portable and the schema is plain Postgres, but the NLP and analytics
  integrations would need adapters elsewhere. For a solo, cost-sensitive project,
  the managed-service leverage outweighs portability
  ([`docs/COST_AND_SCALABILITY.md`](../COST_AND_SCALABILITY.md)).
- **No caching, CDN, or WAF in front of the API.** Not warranted at current
  traffic; the rate limiter is the abuse control that is warranted (§3.1).
- **The database scales vertically only.** Cloud SQL grows by machine size; read
  replicas or Spanner are the documented horizontal path
  ([`docs/COST_AND_SCALABILITY.md` §4](../COST_AND_SCALABILITY.md)).
- **One API version.** The whole surface lives under `/api/v1`
  ([`app/main.py:144-152`](../../app/main.py#L144-L152)); a v2 would be additive,
  not breaking.

---

That is the project as it stands: live at
[aifeelnews-front.web.app](https://aifeelnews-front.web.app), reproducible
without credentials, and written down so it can be checked rather than believed.
What building it taught me — including what went wrong along the way — is in the
self-reflection essay.
