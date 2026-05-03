# aiFeelNews
https://aifeelnews-front.web.app/
> AI-powered news sentiment analysis platform — university assessment project (Cloud Computing, Relational Databases, Cybersecurity)

Ingests articles from Mediastack, crawls original content (respecting robots.txt), runs NLP analysis via Google Cloud Natural Language API (sentiment + entities + classification), and serves everything through a REST API with a Svelte frontend.

## Architecture

### Cloud Infrastructure (GCP + Firebase)
![Cloud Architecture](docs/Cloud_Architecture_Diagram.drawio.png)

### Application Data Flow
![Data Flow](docs/Architechture_diagram-aifeelnews.drawio.png)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI + SQLAlchemy + PostgreSQL 14 (Python 3.13) |
| **Frontend** | Svelte 5 + Vite + TypeScript |
| **Cloud** | GCP Cloud Run, Cloud SQL, Secret Manager, Cloud NL API, Cloud Scheduler, BigQuery, Cloud Monitoring, Cloud Logging |
| **Auth** | Firebase Auth (Google Sign-In) + server-side ID token verification |
| **CI/CD** | GitHub Actions (4 workflows) → Artifact Registry → Cloud Run |
| **IaC** | Terraform |
| **Containers** | 3 Docker images (web, worker, scheduler) |

## Development Setup

### Prerequisites

- Python 3.13+
- Node.js 18+ (frontend)
- Docker + Docker Compose (optional — for full-stack setup)

### Recommended: Docker Compose

The supported local path. The Alembic migration chain uses Postgres-only DDL (views, PL/pgSQL functions, triggers), so a Postgres-backed setup is the path that mirrors production. Compose brings up the database, web, worker, and scheduler in one shot.

```bash
cp .env.example .env                        # committed defaults are sufficient
docker-compose up --build                   # first build ~2-3 min; subsequent boots are seconds
docker-compose exec web python -m app.seeds.seed_db   # bundled 50-article snapshot
```

Frontend runs separately (the SPA is a Vite + Svelte 5 app, not part of Compose):

```bash
cd frontend
cp .env.example .env
echo "VITE_API_BASE_URL=http://localhost:8080" >> .env.local
npm install && npm run dev
```

Backend services:

| Service | Port | Description |
|---------|------|-------------|
| **db** | 5433 | PostgreSQL 14 with persistent volume |
| **web** | 8080 | FastAPI API (migrations run automatically on startup) |
| **worker** | — | Background crawling + NLP analysis on articles in the `crawl_jobs` queue |
| **scheduler** | — | Hourly Mediastack ingestion (only active when `MEDIASTACK_API_KEY` is set) |

API docs are at `http://localhost:8080/docs` (Swagger UI).

### Bare-metal alternative

If you'd rather not use Docker, install PostgreSQL 14 on the host and point `LOCAL_DATABASE_URL` at it:

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env: LOCAL_DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/aifeelnews

alembic upgrade head
python -m app.seeds.seed_db
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

SQLite is **not** a supported substitute for Postgres at the migration layer — the test suite uses SQLite via `Base.metadata.create_all` (which sidesteps migrations), but `alembic upgrade head` against SQLite will fail on the views/functions/triggers DDL.

### Database Setup

| Environment | Database | Configuration |
|-------------|----------|---------------|
| **Docker Compose** | PostgreSQL 14 | Auto-provisioned, port 5433, defaults in `.env.example` |
| **Standalone Postgres** | PostgreSQL 14 | Set `LOCAL_DATABASE_URL=postgresql://user:pass@localhost:5432/aifeelnews_dev` |
| **Tests** | SQLite (in-memory) | Created on the fly via `Base.metadata.create_all` — bypasses migrations |
| **Production** | Cloud SQL | Managed via Terraform — see [Multi-Environment Strategy](docs/MULTI_ENVIRONMENT_STRATEGY.md) |

Schema migrations are managed by Alembic (10 migration files; see [docs/DATABASE.md § 2](docs/DATABASE.md#2-migrations) for the inventory):
```bash
alembic upgrade head              # Apply all pending migrations
alembic downgrade -1              # Rollback last migration
alembic history                   # View migration history
```

**Loading sample data.** A static seed dataset of 50 articles across 10 sources (sampled from production with PII removed) is bundled at `app/seeds/seed_data.json`. Load it after running migrations:

```bash
python -m app.seeds.seed_db          # idempotent: safe to re-run, skips existing URLs
python -m app.seeds.seed_db --reset  # wipe seed rows then reinsert
python -m app.seeds.seed_db --dry-run # show what would be inserted, no commits
```

This is the recommended path for local development and demos — no Mediastack key required. For "production-shape" data, configure `MEDIASTACK_API_KEY` and run `python -m app.jobs.run_ingestion` instead.

### Environment Variables

**Backend** (`.env` — copy from `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `ENV` | No | `local` (default) / `development` / `production` |
| `LOCAL_DATABASE_URL` | No | Default: `sqlite:///./dev.db` |
| `DATABASE_URL` | Docker only | PostgreSQL URL for docker-compose (`postgresql://postgres:pass@db:5432/aifeelnews`) |
| `MEDIASTACK_API_KEY` | For ingestion | Free tier at [mediastack.com](https://mediastack.com) (100 req/month) |
| `SENTIMENT_PROVIDER` | No | `VADER` (free, local) or `GCP_NL` (default, needs GCP credentials) |

**Frontend** (`frontend/.env` — copy from `frontend/.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | Yes | `http://localhost:8000` (local) or `http://localhost:8080` (Docker) |
| `VITE_FIREBASE_*` | For auth | 4 Firebase config values from [Firebase Console](https://console.firebase.google.com) |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /docs` | Interactive OpenAPI documentation |
| `GET /health` | Health check with DB connectivity |
| `GET /ready` | Readiness probe (DB-aware) |
| `GET /version` | Build SHA + timestamp |
| `GET /metrics` | Lightweight observability metrics |
| `GET /articles/`, `GET /articles/{id}`, `GET /articles/latest` | Articles with sentiment data; list routes accept `skip`, `limit`, `sentiment_label`, `category`, `source_id`, `search` |
| `GET /sources/`, `POST /sources/` | News sources |
| `GET/POST/DELETE /bookmarks/...` | User bookmarks (auth required) |
| `GET /api/v1/sentiment/info` | Active sentiment provider |
| `GET /api/v1/entities/`, `GET /api/v1/entities/types`, `GET /api/v1/entities/{id}` | NLP entities (people, orgs, locations) |
| `GET /api/v1/analytics/*` | BigQuery analytics (trends, sources, pipeline stats) |
| `GET /api/v1/db-analytics/*` | PostgreSQL analytics — window functions, CTEs, GROUPING SETS (`/sentiment/rolling`, `/sources/ranked`, `/sentiment/breakdown`, `/entities/momentum`, `/categories/daily`) |
| `POST /api/v1/trigger-ingestion` | Cloud Scheduler: ingest pipeline (OIDC-protected) |
| `POST /api/v1/cleanup` | Cloud Scheduler: TTL cleanup (OIDC-protected) |

> Routers under `/articles`, `/sources`, `/bookmarks`, `/users` are not prefixed with `/api/v1`. The newer analytics + entities + sentiment routers are. This split is historical; standardising the prefix is tracked as a follow-up (`tech-debt: unify API path prefix`).

**Production:** https://aifeelnews-web-813770885946.europe-west1.run.app

## Code Quality

```bash
ruff check app/                   # Lint
ruff format app/                  # Format
mypy app/                         # Type check
pytest tests/ -v                  # Tests
pre-commit run --all-files        # All hooks
```

## Documentation

| Document | Description |
|----------|-------------|
| [Project Structure](docs/PROJECT_STRUCTURE.md) | Full directory layout and architectural patterns |
| [CI/CD Pipeline](docs/CICD_PIPELINE.md) | Pipeline diagram, workflow details, secrets inventory |
| [Multi-Environment Strategy](docs/MULTI_ENVIRONMENT_STRATEGY.md) | Terraform tfvars approach, prod vs staging |
| [Cost & Scalability](docs/COST_AND_SCALABILITY.md) | Monthly breakdown, scaling analysis, cost projections |
| [Threat Model](docs/THREAT_MODEL.md) | STRIDE per component (web, DB, auth, scheduler, CI/CD, ingestion) |
| [Security Measures](docs/SECURITY_MEASURES.md) | Implemented controls catalogued by layer with code citations |

## Key Design Decisions

- **Scale-to-zero** Cloud Run (min=0) — zero cost when idle, cold start acceptable for news analysis
- **OLTP/OLAP separation** — PostgreSQL for API requests, BigQuery for analytics aggregations
- **Single `annotateText` call** — combines sentiment + entities + classification, 66% cost reduction vs separate calls
- **Parameterized queries only** — no f-string SQL anywhere (BigQuery uses `@param` + QueryJobConfig)
- **Data minimization** — article content truncated to 1024 chars with 7-day TTL expiry
- **robots.txt compliance** — honest `aifeelnews-bot/1.0` User-Agent, domain-based rate limiting

## Security

Detailed STRIDE analysis in [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md); the implemented controls are catalogued in [docs/SECURITY_MEASURES.md](docs/SECURITY_MEASURES.md). Quick summary below.

### Authentication & Authorization
- Firebase Auth (Google Sign-In) with server-side ID token verification (`app/deps/auth.py`)
- Protected endpoints require `Authorization: Bearer <firebase-id-token>` header
- User records created on first authenticated request, linked by Firebase UID
- Cloud Scheduler endpoints (`/api/v1/trigger-ingestion`, `/api/v1/cleanup`) require a Google-signed OIDC token verified server-side (`app/deps/oidc.py`)

### Secret Management
- Production: GCP Secret Manager (6 secrets — `db-password`, `mediastack-api-key`, `firebase-service-account-json`, `aifeelnews-gcp-nlp-key`, `aifeelnews-db-password`, `aifeelnews-database-url`)
- `DATABASE_URL` is mounted as a `secretKeyRef` in the Cloud Run revision spec (not a literal env var)
- Cascading lookup: Secret Manager → environment variable → default (`app/utils/secrets.py`)
- No secrets in code or version control — `.env` is gitignored, gitleaks pre-commit + CI scans every commit

### API Security
- CORS restricted to specific origins (Firebase Hosting URLs + localhost) — no wildcard
- Parameterized queries only — no f-string SQL anywhere (BigQuery uses `@param` + `QueryJobConfig`)
- Input validation via Pydantic schemas on all request/response models
- Per-IP rate limiting via `slowapi` — 30/min analytics, 60/min sentiment, 6/h scheduler endpoints

### Data Protection
- Article content truncated to 1024 chars with 7-day TTL expiry (data minimization)
- `robots.txt` compliance with honest `aifeelnews-bot/1.0` User-Agent, domain-based rate limiting
- Never store full article bodies (copyright + privacy)

### Infrastructure Security
- Least-privilege IAM: `cloudrun-sa` (5 roles — `secretmanager.secretAccessor`, `cloudsql.client`, `serviceusage.serviceUsageConsumer`, `bigquery.dataEditor`, `bigquery.jobUser`)
- `github-actions-sa` (6 roles — `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser` on `cloudrun-sa`, `secretmanager.secretAccessor`, `cloudsql.client`, `serviceusage.serviceUsageConsumer`)
- Cloud SQL: SSL enforced (`ssl_mode = "ENCRYPTED_ONLY"` in Terraform) — rejects unencrypted connections
- Migrations run as least-privilege `aifeelnews` Postgres role (no SUPERUSER, no CREATEDB)
- Non-root container users (`app`, `worker`, `scheduler`) in all Docker images
- CI/CD secrets stored in GitHub Secrets, `GCP_SA_KEY` scoped to the `production` GitHub environment

### Supply-Chain Security
- Dependabot (active) — automated security upgrade PRs for `pip` + `npm`
- `pip-audit` weekly + on every PR — fails CI on any pinned dep with a known CVE (`.github/workflows/security.yml`)
- `gitleaks` pre-commit + CI — secret-leak scanner runs locally and on every push (full-history scan + weekly cron)

## License

Educational/research/assessment purposes.
