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

Each use case maps to a backend endpoint and indicates implementation status:
- ✅ Backend implemented
- ⚠️ Partial (backend exists, frontend not wired or missing params)
- 🔲 Not yet implemented

### Casual Reader (P1)

| ID | Use Case | Status | Endpoint | Notes |
|----|----------|--------|----------|-------|
| UC-01 | Browse latest articles | ✅ | `GET /articles/latest?limit=40` | |
| UC-02 | View article detail with sentiment + entities | ✅ | `GET /articles/{id}` | Frontend detail page needed (Phase G) |
| UC-03 | Filter articles by sentiment label | 🔲 | `GET /articles/?sentiment_label=...` | Query param not yet on endpoint |
| UC-04 | Filter articles by category | 🔲 | `GET /articles/?category=...` | Query param not yet on endpoint |
| UC-05 | Filter articles by source | 🔲 | `GET /articles/?source_id=...` | Query param not yet on endpoint |
| UC-06 | Paginate article feed | 🔲 | `GET /articles/?offset=...&limit=...` | Only `limit` exists today |
| UC-07 | Search articles by keyword | 🔲 | `GET /articles/?search=...` | No search param on endpoint |

### Registered Reader (P2)

| ID | Use Case | Status | Endpoint | Notes |
|----|----------|--------|----------|-------|
| UC-08 | Sign in with Google | ✅ | Firebase Auth (Google provider) | |
| UC-09 | Sign in with Email/Password | 🔲 | Firebase Auth (Email provider) | Phase D |
| UC-10 | Bookmark an article | ✅ | `POST /bookmarks/` | Frontend shows "coming soon" alert |
| UC-11 | View bookmarks list | ✅ | `GET /bookmarks/` | Frontend page needed (Phase G) |
| UC-12 | Remove a bookmark | ✅ | `DELETE /bookmarks/{id}` | |

### News Analyst (P3)

| ID | Use Case | Status | Endpoint | Notes |
|----|----------|--------|----------|-------|
| UC-13 | View sentiment trends over time | ✅ | `GET /api/v1/analytics/trends?days=30` | |
| UC-14 | Compare sources by sentiment | ✅ | `GET /api/v1/analytics/sources?days=30` | |
| UC-15 | View top entities by mention count | ✅ | `GET /api/v1/analytics/entities/top` | |
| UC-16 | View entity sentiment distribution | ✅ | `GET /api/v1/analytics/entities/sentiment` | |
| UC-17 | View NLP category breakdown | ✅ | `GET /api/v1/analytics/categories/nlp` | |
| UC-18 | Browse entity directory | ✅ | `GET /api/v1/entities/?entity_type=...` | |
| UC-19 | View entity detail | ✅ | `GET /api/v1/entities/{id}` | |

### System Administrator (P4)

| ID | Use Case | Status | Endpoint | Notes |
|----|----------|--------|----------|-------|
| UC-20 | Trigger manual ingestion | ✅ | `POST /api/v1/trigger-ingestion` | Needs OIDC auth (Phase D) |
| UC-21 | View pipeline health metrics | ✅ | `GET /api/v1/analytics/pipeline?days=7` | |
| UC-22 | Run TTL content cleanup | ✅ | `POST /api/v1/cleanup` | Needs OIDC auth (Phase D) |

---

## Use Case Summary

| Status | Count | Notes |
|--------|-------|-------|
| ✅ Implemented | 14 | Backend fully functional |
| ⚠️ Partial | 0 | — |
| 🔲 Planned | 8 | Filtering, pagination, search, Email auth, frontend wiring |

**Total: 22 use cases across 4 personas**

---

## Traceability Matrix

A traceability matrix connects requirements (use cases) to implementation (tables, phases, endpoints). It ensures every table in the schema serves at least one real user need, and every planned feature traces back to a persona.

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

### Phases → Use Cases (implementation view)

| Phase | Use Cases Addressed | What It Delivers |
|-------|---------------------|------------------|
| **B** (DB Excellence) | UC-03–07 | Filtering, pagination, search — requires new query params + indexes |
| **D** (Auth + Security) | UC-09, UC-20, UC-22 | Email/Password sign-in, OIDC on admin endpoints |
| **F** (BigQuery) | UC-13–17 | Richer analytics queries powering dashboard charts |
| **G** (Frontend) | UC-02, UC-06–07, UC-10–11 | Article detail page, pagination/search UI, bookmarks page |
