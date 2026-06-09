# aiFeelNews - Project Structure

## Root Directory

```
aifeelnews/
├── .github/workflows/          # CI/CD pipelines (4 workflows)
├── alembic/                    # Database migrations (SQLAlchemy)
├── app/                        # Backend application (FastAPI)
├── docker/                     # Container definitions (3 images)
├── docs/                       # Architecture diagrams & documentation
├── frontend/                   # Svelte 5 SPA (Firebase Hosting)
├── infra/                      # Terraform IaC
├── scripts/                    # Utility and setup scripts
├── tests/                      # pytest test suite
├── .pre-commit-config.yaml     # Pre-commit hooks (ruff, mypy)
├── alembic.ini                 # Alembic migration config
├── docker-compose.yml          # Local development stack
├── docker-compose.prod.yml     # Production-like stack
├── pyproject.toml              # Python metadata, ruff, mypy config
├── pytest.ini                  # Test configuration
└── requirements.txt            # Python dependencies
```

## Backend Application (`app/`)

```
app/
├── main.py                     # FastAPI entry point, router registration
├── database.py                 # SQLAlchemy engine + session factory
│
├── config/                     # Pydantic BaseSettings (one per concern)
│   ├── __init__.py             # AppConfig aggregator (all configs)
│   ├── bigquery.py             # BigQuery: dataset, location, batch size
│   ├── crawler.py              # Crawler: user-agent, timeouts, robots.txt
│   ├── database.py             # DB: connection string, pool settings
│   ├── ingestion.py            # Ingestion: Mediastack API, article limits
│   ├── scheduler.py            # Scheduler: cron expressions
│   ├── sentiment.py            # Sentiment: provider selection, thresholds
│   └── ui.py                   # UI: CORS origins, frontend URL
│
├── deps/                       # FastAPI dependency injection
│   └── auth.py                 # Firebase token verification (get_current_user)
│
├── crud/                       # Hand-written query layer (advanced SQL)
│   ├── analytics.py            # Window functions, CTEs, GROUPING SETS (+ EN/DE language filter)
│   └── search.py               # Full-text search (tsvector + ts_rank), per-language EN/DE config
│
├── jobs/                       # Pipeline & background tasks
│   ├── run_ingestion.py        # Orchestrator: fetch → normalize → ingest → crawl
│   ├── fetch_from_mediastack.py # Mediastack API client
│   ├── normalize_articles.py   # Raw → structured article normalization
│   ├── ingest_articles.py      # Upsert articles + sources into PostgreSQL
│   ├── crawl_worker.py         # Content crawling + NLP analysis pipeline
│   ├── sources_list.py         # Source definitions (EN + DE national outlets)
│   ├── backfill_german.py      # One-time historical German ingest (Mediastack → Postgres + NLP)
│   └── ttl_cleanup.py          # Expired content removal (Cloud Scheduler)
│
├── models/                     # SQLAlchemy ORM models
│   ├── __init__.py             # Model registry (imports all models)
│   ├── article.py              # Article (core entity)
│   ├── article_category.py     # Article ↔ Category (M2M via NLP)
│   ├── article_content.py      # Crawled content with TTL expiry
│   ├── article_entity.py       # Article ↔ Entity (M2M via NLP)
│   ├── bookmark.py             # User bookmarks (M2M: users ↔ articles)
│   ├── crawl_job.py            # Crawl job tracking and status
│   ├── entity.py               # Named entities (people, orgs, locations)
│   ├── sentiment_analysis.py   # Per-article sentiment scores
│   ├── source.py               # News sources (BBC, CNN, etc.)
│   └── user.py                 # User accounts (Firebase UID)
│
├── routers/                    # FastAPI route handlers
│   ├── analytics.py            # GET /api/v1/analytics/* (BigQuery OLAP)
│   ├── articles.py             # GET /api/v1/articles, search, filters
│   ├── bookmarks.py            # CRUD /api/v1/bookmarks (auth required)
│   ├── entities.py             # GET /api/v1/entities (NLP extracted)
│   ├── sentiment.py            # GET /api/v1/sentiment/summary, distribution
│   ├── sources.py              # GET /api/v1/sources
│   └── users.py                # GET/POST /api/v1/users (profile)
│
├── schemas/                    # Pydantic request/response models
│   ├── analytics.py            # Trend points, source comparison, pipeline stats
│   ├── article.py              # Article list/detail responses
│   ├── bookmark.py             # Bookmark create/response
│   ├── entity.py               # Entity with mention counts
│   ├── source.py               # Source metadata
│   └── user.py                 # User profile
│
├── services/                   # External service integrations
│   ├── bigquery.py             # BigQuery: batch streaming, analytics queries
│   └── firebase_admin.py       # Firebase Admin SDK initialization
│
└── utils/                      # Shared utilities
    ├── cleanup.py              # TTL enforcement helpers
    ├── gcp_nlp.py              # Google Cloud NL API (annotateText)
    ├── logging.py              # Structured logging configuration
    ├── robots.py               # robots.txt parser and compliance
    ├── secrets.py              # get_secret_or_env() cascading lookup
    ├── sentiment.py            # Multi-provider sentiment (GCP NL + VADER)
    └── ttl.py                  # TTL calculation utilities
```

## Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── App.svelte              # Root component (routing, layout)
│   ├── main.ts                 # Entry point
│   ├── app.css                 # Global styles
│   └── lib/
│       ├── api.ts              # Backend API client (fetch wrapper)
│       └── firebase.ts         # Firebase Auth initialization
├── index.html                  # SPA entry HTML
├── firebase.json               # Firebase Hosting config
├── vite.config.ts              # Vite build configuration
├── svelte.config.js            # Svelte compiler options
└── package.json                # Node dependencies
```

## Infrastructure (`infra/`)

```
infra/
├── main.tf                     # All GCP resources (Cloud SQL, Scheduler, BQ, IAM)
├── variables.tf                # Input variable declarations
├── outputs.tf                  # Output values (URLs, instance names)
└── envs/
    ├── prod.tfvars             # Production values (active)
    └── staging.tfvars          # Staging values (ready to activate)
```

## CI/CD Pipelines (`.github/workflows/`)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy.yml` | Push/PR to main | Lint (ruff) → type-check (mypy) → test (pytest) → build Docker → deploy Cloud Run |
| `firebase-hosting-merge.yml` | Push to main | Build frontend → deploy to Firebase Hosting (live) |
| `firebase-hosting-pull-request.yml` | Any PR | Build frontend → deploy to Firebase Hosting (preview) |
| `auto-review.yml` | PR opened | Request GitHub Copilot review |

## Docker (`docker/`)

```
docker/
├── Dockerfile.web              # FastAPI API server (uvicorn)
├── Dockerfile.worker           # Ingestion pipeline worker
├── Dockerfile.scheduler        # Cloud Scheduler target (TTL cleanup)
├── startup.sh                  # Container entrypoint (runs migrations)
└── README.md                   # Container architecture notes
```

## Database Migrations (`alembic/`)

17 migration files tracking schema evolution from initial tables through entity extraction, Firebase auth, and full-text search (English + German `tsvector` columns). See [docs/DATABASE.md § 2](DATABASE.md#2-migrations) for the full inventory.

## Tests (`tests/`)

```
tests/
├── conftest.py                 # Fixtures: SQLite test DB, mock config
├── test_bigquery.py            # BigQuery service: config, buffering, graceful degradation
├── test_crawl_worker.py        # Crawl pipeline unit tests
├── test_ingestion.py           # Ingestion pipeline tests
└── test_new_models.py          # ORM model relationship tests
```

## Code Quality

| Tool | Purpose | Config |
|------|---------|--------|
| **Ruff** | Linting + formatting (replaces Black, isort, flake8) | `pyproject.toml` |
| **mypy** | Static type checking | `pyproject.toml` |
| **pre-commit** | Git hooks (ruff, mypy, trailing whitespace) | `.pre-commit-config.yaml` |
| **pytest** | Test runner | `pytest.ini` |

## Key Architectural Patterns

- **Config per concern**: Each `app/config/*.py` is a Pydantic `BaseSettings` class, accessed via `from app.config import config`
- **Cascading secrets**: `get_secret_or_env(secret_name, env_var, default)` — Secret Manager → env var → default
- **Graceful router imports**: Routers with optional dependencies use try/except import with `_available` flag
- **OLTP/OLAP separation**: PostgreSQL handles API requests, BigQuery handles analytics aggregations
- **Lazy service clients**: BigQuery and Firebase Admin initialize on first use, not at import time
- **Scale-to-zero**: Cloud Run min-instances=0 with Cloud Scheduler for periodic tasks
