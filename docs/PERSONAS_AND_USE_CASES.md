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
| **Behaviour** | Signs in (Google or Email/Password), bookmarks articles for later, revisits bookmarks page |
| **Auth** | Required (Firebase Auth — Google Sign-In or Email/Password) |
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
| **Goal** | Ensure the ingestion pipeline runs reliably and data quality stays high |
| **Behaviour** | Checks pipeline health metrics, triggers manual ingestion when needed, monitors crawl job success rates |
| **Auth** | Required (OIDC-verified for scheduler endpoints) |
| **Key needs** | Pipeline health dashboard, manual trigger capability, TTL cleanup controls |
| **Frequency** | Ad-hoc, during incidents or after deployment |

---

## Use Cases

Each use case has two status columns — backend (the API/data layer) and UI (what the SPA actually exposes to a user) — because the two can move at different speeds:

- ✅ Implemented
- 🔲 Not yet implemented
- `n/a` Not user-facing (e.g. P4 admin scheduler triggers don't have a UI by design)

### Casual Reader (P1)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-01 | Browse latest articles | ✅ | ✅ | `GET /articles/latest?limit=40` | |
| UC-02 | View article detail with sentiment + entities | ✅ | 🔲 | `GET /articles/{id}` | Detail page deferred — feed cards already show sentiment badge |
| UC-03 | Filter articles by sentiment label | ✅ | ✅ | `GET /articles/?sentiment_label=...` | |
| UC-04 | Filter articles by category | ✅ | ✅ | `GET /articles/?category=...` | UI uses static mediastack enum; categories endpoint deferred |
| UC-05 | Filter articles by source | ✅ | ✅ | `GET /articles/?source_id=...` | UI populates dropdown from `GET /sources/` |
| UC-06 | Paginate article feed | ✅ | ✅ | `GET /articles/?skip=...&limit=...` | |
| UC-07 | Search articles by keyword | ✅ | ✅ | `GET /articles/?search=...` | ILIKE substring on title; pg_trgm upgrade path documented in DATABASE.md |

### Registered Reader (P2)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-08 | Sign in with Google | ✅ | ✅ | Firebase Auth (Google provider) | |
| UC-09 | Sign in with Email/Password | 🔲 | 🔲 | Firebase Auth (Email provider) | Phase D — risk of regressing working Google sign-in, deferred |
| UC-10 | Bookmark an article | ✅ | ✅ | `POST /bookmarks/` | Optimistic UI; 409 treated as silent success |
| UC-11 | View bookmarks list | ✅ | ✅ | `GET /bookmarks/` | Dedicated `/bookmarks` view in SPA |
| UC-12 | Remove a bookmark | ✅ | ✅ | `DELETE /bookmarks/{id}` | Optimistic remove with revert-on-error |

### News Analyst (P3)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-13 | View sentiment trends over time | ✅ | ✅ | `GET /api/v1/analytics/trends?days=30` | Analytics dashboard, "Sentiment Trends" chart |
| UC-14 | Compare sources by sentiment | ✅ | ✅ | `GET /api/v1/analytics/sources?days=30` | Analytics dashboard, "Source Comparison" chart |
| UC-15 | View top entities by mention count | ✅ | ✅ | `GET /api/v1/analytics/entities/top` | Analytics dashboard, "Top Entities" chart |
| UC-16 | View entity sentiment distribution | ✅ | 🔲 | `GET /api/v1/analytics/entities/sentiment` | |
| UC-17 | View NLP category breakdown | ✅ | ✅ | `GET /api/v1/analytics/categories/nlp` | Analytics dashboard, "GCP NL Categories" chart |
| UC-18 | Browse entity directory | ✅ | 🔲 | `GET /api/v1/entities/?entity_type=...` | |
| UC-19 | View entity detail | ✅ | 🔲 | `GET /api/v1/entities/{id}` | |

### System Administrator (P4)

| ID | Use Case | Backend | UI | Endpoint | Notes |
|----|----------|---------|----|----------|-------|
| UC-20 | Trigger manual ingestion | ✅ | n/a | `POST /api/v1/trigger-ingestion` | Cloud Scheduler-driven, OIDC-verified |
| UC-21 | View pipeline health metrics | ✅ | n/a | `GET /api/v1/analytics/pipeline?days=7` | Available to operators via API + GCP console |
| UC-22 | Run TTL content cleanup | ✅ | n/a | `POST /api/v1/cleanup` | Cloud Scheduler-driven, OIDC-verified |

---

## Use Case Summary

| Persona | Backend ✅ | UI ✅ | UI 🔲 | UI n/a | Backend 🔲 |
|---------|-----------|------|------|--------|-----------|
| P1 Casual Reader | 7 / 7 | 6 / 7 | 1 (UC-02) | 0 | 0 |
| P2 Registered Reader | 4 / 5 | 4 / 5 | 0 | 0 | 1 (UC-09) |
| P3 News Analyst | 7 / 7 | 4 / 7 | 3 (UC-16, UC-18, UC-19) | 0 | 0 |
| P4 System Administrator | 3 / 3 | n/a | n/a | 3 | 0 |
| **Totals** | **21 / 22** | **14 / 19 user-facing** | **5** | **3** | **1** |

User-facing UC count excludes P4 (scheduler-driven, no UI by design).

---

## Roadmap for not-yet-implemented use cases

| ID | Status | Plan |
|----|--------|------|
| UC-02 | UI 🔲 | Article detail page — Svelte route showing full content, entities, sentiment scores. Backend ready. |
| UC-09 | Backend + UI 🔲 | Email/Password sign-in via Firebase Auth. Deferred because it touches the working Google flow. |
| UC-16 | UI 🔲 | Entity sentiment-distribution chart. Backend ready; not yet on the dashboard. |
| UC-18, UC-19 | UI 🔲 | Entity directory list + detail page. Backend ready. |

---

## Traceability Matrix

A traceability matrix connects requirements (use cases) to implementation (tables, endpoints). It ensures every table in the schema serves at least one real user need, and every planned feature traces back to a persona.

### Tables → Use Cases (DB-centric view)

| Table | Use Cases | Why This Table Exists |
|-------|-----------|----------------------|
| `sources` | UC-05, UC-14 | Filter by source, compare source sentiment bias |
| `articles` | UC-01–07 | Core content — every Casual Reader use case hits this table |
| `bookmarks` | UC-10–12 | M2M join enabling Registered Reader's personal reading list |
| `users` | UC-08–09, UC-10–12 | Auth identity; FK anchor for bookmarks |
| `article_contents` | UC-02 | Crawled body text shown on article detail page |
| `sentiment_analyses` | UC-02, UC-13–14 | Multi-provider scores drive sentiment badges and trend charts |
| `entities` | UC-15–16, UC-18–19 | Canonical entity lookup for News Analyst tracking |
| `article_entities` | UC-15–16, UC-18 | M2M with payload — salience/mention_count power entity analytics |
| `article_categories` | UC-04, UC-17 | NLP classification enables category filtering and heatmaps |
| `crawl_jobs` | UC-21 | Pipeline health metrics for System Admin |
