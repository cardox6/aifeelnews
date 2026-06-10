# Personas & Use Cases — aiFeelNews

## Personas

### P1: Casual Reader

| Attribute | Detail |
|-----------|--------|
| **Goal** | Stay informed with sentiment-aware news at a glance |
| **Behaviour** | Opens the feed, scans headlines and sentiment badges, clicks articles that stand out |
| **Auth** | None required |
| **Key needs** | Fast feed loading, clear sentiment indicators, filter by category/source/sentiment |
| **Frequency** | Daily, 2–5 min sessions |

### P2: Registered Reader

| Attribute | Detail |
|-----------|--------|
| **Goal** | Curate a personal reading list and track preferred topics |
| **Behaviour** | Signs in with Google, bookmarks articles for later, revisits bookmarks page |
| **Auth** | Required (Firebase Auth — Google Sign-In) |
| **Key needs** | Persistent bookmarks, quick sign-in, bookmark management |
| **Frequency** | Daily, 5–10 min sessions |

### P3: News Analyst

| Attribute | Detail |
|-----------|--------|
| **Goal** | Discover sentiment trends, source bias, and entity-level patterns |
| **Behaviour** | Navigates to analytics dashboard, compares sources, tracks entity sentiment over time, exports insights |
| **Auth** | Required |
| **Key needs** | Trend charts, entity tracking, source comparison, category heatmaps, date-range controls |
| **Frequency** | Weekly, 10–20 min deep-dive sessions |

### P4: System Administrator

| Attribute | Detail |
|-----------|--------|
| **Goal** | Ensure the ingestion pipeline runs reliably, data quality stays high, and privileged writes stay locked down |
| **Behaviour** | Checks pipeline health metrics, triggers manual ingestion when needed, monitors crawl job success rates, registers new news sources |
| **Auth** | Required — automated jobs are OIDC-verified; human admin writes are gated by an `admin` role claim (Firebase custom claims, `require_admin`) |
| **Key needs** | Pipeline health dashboard, manual trigger capability, TTL cleanup controls, admin-only source registration |
| **Frequency** | Ad-hoc, during incidents or after deployment |

---

## Use Cases

Each use case has two status columns — backend (the API/data layer) and UI (what the SPA actually exposes to a user) — because the two can move at different speeds:

- ✅ Implemented
- 🔲 Not yet implemented (on the backlog)
- ⬚ Decided against — a deliberate non-goal, not a pending item
- `n/a` Not user-facing (e.g. P4 admin scheduler triggers don't have a UI by design)

### Casual Reader (P1)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-01 | Browse latest articles | ✅ | ✅ | `GET /api/v1/articles/latest?limit=40` | |
| UC-02 | View article detail with sentiment + entities | ✅ | 🔲 | `GET /api/v1/articles/{id}` | Detail page deferred — feed cards already show sentiment badge |
| UC-03 | Filter articles by sentiment label | ✅ | ✅ | `GET /api/v1/articles/?sentiment_label=...` | |
| UC-04 | Filter articles by category | ✅ | ✅ | `GET /api/v1/articles/?category=...` | UI uses static mediastack enum; categories endpoint deferred |
| UC-05 | Filter articles by source | ✅ | ✅ | `GET /api/v1/articles/?source_id=...` | UI populates the dropdown from `GET /api/v1/sources/?language=<en\|de>`, which returns only sources that have articles in the current language (derived via a JOIN, not a stored column) so the filter can't offer a source that yields an empty feed |
| UC-06 | Paginate article feed | ✅ | ✅ | `GET /api/v1/articles/?skip=...&limit=...` | |
| UC-07 | Search articles by keyword | ✅ | ✅ | `GET /api/v1/articles/?search=...` | ILIKE substring on title, **pg_trgm GIN-indexed** + `similarity()` ranking on Postgres (shipped — DATABASE.md § 4.4) |
| UC-26 | Full-text search (phrases, boolean, ranked) | ✅ | ✅ | `GET /api/v1/articles/search?q=...` | `tsvector` + `ts_rank`; `websearch_to_tsquery` grammar (quoted phrases, `or`, leading `-`); language-aware stemming (EN/DE) |
| UC-27 | Filter the feed + dashboard by language (EN/DE toggle) | ✅ | ✅ | `GET /api/v1/articles/?language=de` | Header flag toggle switches the whole feed, the analytics dashboard, **and** the source-filter dropdown (which re-scopes to the language's sources); persisted to the URL (`?lang=de`) |
| UC-28 | Date-range filter on the feed | ✅ | ✅ | `GET /api/v1/articles/?published_after=...&published_before=...` | Preset + custom ranges in the FilterBar |

### Registered Reader (P2)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-08 | Sign in with Google | ✅ | ✅ | Firebase Auth (Google provider) | |
| UC-09 | Sign in with Email/Password | ⬚ | ⬚ | — | **Decided against** (not a backlog item). The access-control story is RBAC via Firebase custom claims, not a second credential flow; adding Email/Password would risk regressing the working Google flow for little return. See note below. |
| UC-10 | Bookmark an article | ✅ | ✅ | `POST /api/v1/bookmarks/` | Optimistic UI; 409 treated as silent success |
| UC-11 | View bookmarks list | ✅ | ✅ | `GET /api/v1/bookmarks/` | Dedicated `/bookmarks` view in SPA |
| UC-12 | Remove a bookmark | ✅ | ✅ | `DELETE /api/v1/bookmarks/{id}` | Optimistic remove with revert-on-error |

### News Analyst (P3)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-13 | View sentiment trends over time | ✅ | ✅ | `GET /api/v1/analytics/trends?days=30` | Analytics dashboard, "Sentiment Trends" chart |
| UC-14 | Compare sources by sentiment | ✅ | ✅ | `GET /api/v1/analytics/sources?days=30` | Analytics dashboard, "Source Comparison" chart |
| UC-15 | View top entities by mention count | ✅ | ✅ | `GET /api/v1/analytics/entities/top` | Analytics dashboard, "Most-Mentioned People & Organizations" chart; entity-type filter (PERSON/ORGANIZATION/…). A quality gate (Knowledge-Graph-resolved entities + a publisher denylist) keeps publishers/wire-services out — see [DATABASE.md § 4.3a](DATABASE.md#43a-entity-quality-gate) |
| UC-16 | View entity sentiment distribution | ✅ | ✅ | `GET /api/v1/analytics/entities/sentiment` | Analytics dashboard, "Most Positively & Negatively Covered Names" chart; entity-type filter (PERSON/ORGANIZATION/…) |
| UC-17 | View NLP category breakdown | ✅ | ✅ | `GET /api/v1/analytics/categories/nlp` | Analytics dashboard, "GCP NL Categories" chart |
| UC-18 | Browse entity directory | ✅ | 🔲 | `GET /api/v1/entities/?entity_type=...` | |
| UC-19 | View entity detail | ✅ | 🔲 | `GET /api/v1/entities/{id}` | |
| UC-24 | View advanced-SQL trend charts (rolling avg, source ranking, category breakdown) | ✅ | ✅ | `GET /api/v1/db-analytics/*` | Analytics dashboard — PostgreSQL window-function/CTE/GROUPING SETS charts. Backed by the operational DB, so these **populate in demo mode** (no BigQuery/GCP-NL needed), unlike the GCP-NL-backed UC-15/16/17 entity & category charts |
| UC-25 | View per-entity sentiment trend over time | ✅ | ✅ | `GET /api/v1/analytics/entities/sentiment-timeline` | Analytics dashboard, "How Coverage Sentiment Shifts Over Time" — BigQuery-native daily timeline for the top-N entities; fulfils P3's "tracks entity sentiment over time" goal |

### System Administrator (P4)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-20 | Trigger manual ingestion | ✅ | n/a | `POST /api/v1/trigger-ingestion` | Cloud Scheduler-driven, OIDC-verified |
| UC-21 | View pipeline health metrics | ✅ | n/a | `GET /api/v1/analytics/pipeline?days=7` | Available to operators via API + GCP console |
| UC-22 | Run TTL content cleanup | ✅ | n/a | `POST /api/v1/cleanup` | Cloud Scheduler-driven, OIDC-verified |
| UC-23 | Register a new news source (admin) | ✅ | n/a | `POST /api/v1/sources/` | Gated by `require_admin` — caller's Firebase ID token must carry an `admin` role claim (custom claims). Non-admins get 403, unauthenticated 401 |

---

## Use Case Summary

| Persona | Backend ✅ | UI ✅ | UI 🔲 | UI n/a | Backlog 🔲 |
|---------|-----------|------|------|--------|-----------|
| P1 Casual Reader | 10 / 10 | 9 / 10 | 1 (UC-02) | 0 | 0 |
| P2 Registered Reader | 4 / 4 | 4 / 4 | 0 | 0 | 0 |
| P3 News Analyst | 9 / 9 | 7 / 9 | 2 (UC-18, UC-19) | 0 | 0 |
| P4 System Administrator | 4 / 4 | n/a | n/a | 4 | 0 |
| **Totals** | **27 / 27** | **20 / 23 user-facing** | **3** | **4** | **0** |

Every defined use case has its backend implemented. UC-09 (Email/Password sign-in) is excluded from these counts — it is a deliberate non-goal (⬚), not a backlog gap (see the note under the Registered Reader table and the Roadmap section). User-facing UI counts exclude P4 (scheduler/admin-driven, no UI by design).

---

## Roadmap for not-yet-implemented use cases

These are UI-only gaps — the backend is implemented in every case; only the SPA surface is outstanding.

| ID | Status | Plan |
|----|--------|------|
| UC-02 | UI 🔲 | Article detail page — Svelte route showing full content, entities, sentiment scores. Backend ready. |
| UC-18, UC-19 | UI 🔲 | Entity directory list + detail page. Backend ready. |

### Deliberate non-goals

| ID | Decision | Rationale |
|----|----------|-----------|
| UC-09 | ⬚ Email/Password sign-in — **decided against** | The access-control story is **RBAC via Firebase custom claims** (an `admin` role claim read from the Google-signed token, gating `POST /api/v1/sources/` via `require_admin`), not a second credential flow. A separate Email/Password path would add surface area and risk regressing the working Google Sign-In for no proportional gain. The original Exposé listed it as planned; this is the considered decision not to pursue it. |

---

## Traceability Matrix

A traceability matrix connects requirements (use cases) to implementation (tables, endpoints). It ensures every table in the schema serves at least one real user need, and every planned feature traces back to a persona.

### Tables → Use Cases (DB-centric view)

| Table | Use Cases | Why This Table Exists |
|-------|-----------|----------------------|
| `sources` | UC-05, UC-14, UC-23, UC-24 | Filter by source, compare/rank source sentiment bias, admin source registration |
| `articles` | UC-01–07, UC-24 | Core content — every Casual Reader use case hits this table; also the basis of the db-analytics trend charts |
| `bookmarks` | UC-10–12 | M2M join enabling Registered Reader's personal reading list |
| `users` | UC-08, UC-10–12 | Auth identity; FK anchor for bookmarks. The `admin` authorization role rides in the Firebase ID token (custom claim), so it needs no column here |
| `article_contents` | UC-02 | Crawled body text shown on article detail page |
| `sentiment_analyses` | UC-02, UC-13–14, UC-24 | Multi-provider scores drive sentiment badges, trend charts, and the rolling-average/ranking db-analytics queries |
| `entities` | UC-15–16, UC-18–19, UC-25 | Canonical entity lookup for News Analyst tracking + per-entity sentiment timeline |
| `article_entities` | UC-15–16, UC-18, UC-24, UC-25 | M2M with payload — salience/mention_count power entity analytics + the entity-momentum and sentiment-timeline queries |
| `article_categories` | UC-04, UC-17, UC-24 | NLP classification enables category filtering, heatmaps, and the daily-category breakdown |
| `crawl_jobs` | UC-21 | Pipeline health metrics for System Admin |
