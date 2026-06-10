# aiFeelNews
https://aifeelnews-front.web.app/
> AI-powered news sentiment analysis platform — university assessment project (Cloud Computing, Relational Databases, Cybersecurity)

Ingests **English and German** articles from Mediastack, crawls original content (respecting robots.txt), runs NLP analysis via Google Cloud Natural Language API (sentiment + entities + classification, per-language), and serves everything through a REST API with a Svelte frontend. The frontend has an EN/DE flag toggle that switches both the article feed and the analytics dashboard between languages.

## Architecture

### Cloud Infrastructure (GCP + Firebase)
![Cloud Architecture](docs/Cloud_Architecture_Diagram.drawio.png)

### Application Data Flow
![Data Flow](docs/Architechture_diagram-aifeelnews.drawio.png)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI + SQLAlchemy + PostgreSQL 14 (Python 3.14) |
| **Frontend** | Svelte 5 + Vite + TypeScript |
| **Cloud** | GCP Cloud Run, Cloud SQL, Secret Manager, Cloud NL API, Cloud Scheduler, BigQuery, Cloud Monitoring, Cloud Logging |
| **Auth** | Firebase Auth (Google Sign-In) + server-side ID token verification |
| **CI/CD** | GitHub Actions (6 workflows) → Artifact Registry → Cloud Run |
| **IaC** | Terraform |
| **Containers** | 3 Docker images (web, worker, scheduler) |

## Development Setup

### Prerequisites

- Docker + Docker Compose (recommended — supported full-stack path)
- Python 3.14+ (only if running the backend on the host instead of in Compose)
- Node.js 18+ (frontend dev server)

### Two run modes

The project has two distinct local-run modes:

| Mode | Sentiment | Articles | Credentials needed |
|---|---|---|---|
| **Demo** (default in `.env.example`) | VADER | Bundled seed dataset (75 articles, English + German) | None |
| **Production-equivalent** | GCP NL (entities + categories) | Live Mediastack ingestion | GCP service account JSON + paid Mediastack key |

Demo mode is fully self-contained — no API keys, no GCP project. The bundled seed is a **fully enriched** production sample: 75 articles (50 English + 25 German) with sentiment, magnitude, GCP-NL entities, and topic categories pre-populated, spread across several days so the trend lines show a real tendency. The seeder anchors the dates so the newest article lands ~1 day ago (the default *Last 30 days* dashboard range always has data), and shifts the entity/category `analyzed_at` timestamps by the same offset so the trending-names window stays valid. The six Analytics charts backed by the PostgreSQL `db-analytics` endpoints — mood-over-time (rolling average), source ranking, sentiment-by-category, **trending names** (entity momentum), and cumulative volume — populate out of the box, because they query the operational database (which the seed enriches) directly rather than BigQuery. The "AI-Enriched Insights" row (Top Entities + topic classification) is **BigQuery**-backed and stays empty in demo mode, since BigQuery streaming requires a GCP project; the same entity/category data is present in Postgres, so the trending-names chart still renders. Running the worker with `--queue-crawl-jobs` (see below) populates `article_contents` and `sentiment_analyses` from the live article URLs.

Production-equivalent mode requires real credentials: a GCP service account JSON with the Cloud Natural Language API enabled, and a paid Mediastack key — the free tier is HTTP-only and the project enforces HTTPS in [`app/config/ingestion.py:7`](app/config/ingestion.py#L7), so a free key will not authenticate. Both are project secrets and not shipped with the repo.

### Recommended: Docker Compose

The Alembic migration chain uses Postgres-only DDL (views, PL/pgSQL functions, triggers), so a Postgres-backed setup is the path that mirrors production. The fastest clean start is one command:

```bash
cp .env.example .env   # committed defaults run demo mode — no API keys
make demo              # build, start Postgres + web, wait healthy, load the seed
```

`make demo` brings up **only** Postgres and the web API, then loads the bundled enriched bilingual seed — a deterministic 75-article (50 EN + 25 DE) dataset with sentiment, magnitude, entities, and categories, so every analytics chart populates offline. Open <http://localhost:8002/docs>. The worker and scheduler are **not** started by default, so nothing pulls live data over the seed and the dataset is reproducible run-to-run.

> `make` shells out to `sh`; on Windows use Git Bash / WSL, or run the equivalent raw commands below. Other handy targets: `make seed` / `make seed-reset` (reload the seed), `make down`, `make logs`.

Raw Compose, if you prefer not to use `make`:

```bash
docker compose up --build -d db web                  # db + web only (the default profile)
docker compose exec web python -m app.seeds.seed_db  # load the bundled enriched seed
```

To exercise the **full ingestion pipeline** (live Mediastack fetch + robots.txt-respecting crawl + sentiment/entity analysis), opt in to the `pipeline` profile, which adds the worker and the hourly scheduler. This needs a paid Mediastack key in `.env` to fetch new articles:

```bash
make pipeline-up                                     # or: docker compose --profile pipeline up --build -d
docker compose logs -f worker                        # watch the worker drain the crawl queue
```

Alternatively, queue crawl jobs for the **seeded** article URLs without live ingestion, then start the worker:

```bash
docker compose exec web python -m app.seeds.seed_db --queue-crawl-jobs
docker compose --profile pipeline up -d worker
```

The seed URLs are real public URLs (BBC, NYTimes, Spiegel, etc., sampled from production). Some will not crawl successfully — they may have been moved or removed (`status=FAILED`), be denied by `robots.txt` (`status=FORBIDDEN_BY_ROBOTS`), or hit the per-host rate limit (`status=RATE_LIMITED`, retried later). That is the intended behavior of the worker; failures are surfaced in `crawl_jobs.status` and visible at `GET /metrics`.

Frontend runs separately (the SPA is a Vite + Svelte 5 app, not part of Compose). With the demo backend already up (`make demo`), this is all it takes:

```bash
cd frontend
cp .env.example .env
# For the docker-compose backend: no override needed — api.ts auto-detects
# localhost and uses DEFAULT_LOCAL_API_BASE (http://127.0.0.1:8002).
# Set VITE_API_BASE_URL in .env.local only if you need a non-default host/port.
npm install && npm run dev   # → http://localhost:5173
```

Both the **article feed** and the full **Analytics dashboard** (mood-over-time, source ranking, sentiment-by-category, trending names, cumulative volume) load **without signing in** — they read only public, unauthenticated endpoints. The Firebase keys in `.env.example` are placeholders; the app falls back to a no-auth demo mode (a harmless "Firebase not configured" console note). The **only** feature that needs real Firebase config is **Sign in with Google → Bookmarks** (per-user data). So an assessor can boot the entire project, browse the EN/DE feed, and explore every chart with **zero credentials**. The "AI-Enriched Insights" row (Top Entities / topic classification) is BigQuery-backed and stays empty offline — the same entity data drives the trending-names chart from Postgres.

Backend services:

| Service | Host port | Container port | Description |
|---------|-----------|----------------|-------------|
| **db** | 5433 | 5432 | PostgreSQL 14 with persistent volume |
| **web** | 8002 | 8080 | FastAPI API (migrations run automatically on startup). Host port is `:8002` (not `:8080`) to sidestep a local Apache/XAMPP that often squats on `:8080` on Windows. The container itself, prod compose, and Cloud Run all stay on `:8080`. |
| **worker** | — | — | Background crawling + NLP analysis on articles in the `crawl_jobs` queue |
| **scheduler** | — | — | Hourly Mediastack ingestion (only active when `MEDIASTACK_API_KEY` is set) |

API docs are at `http://localhost:8002/docs` (Swagger UI).

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

SQLite is **not** a supported substitute for Postgres at the migration layer — the backend test suite uses SQLite via `Base.metadata.create_all` (which sidesteps migrations), but `alembic upgrade head` against SQLite will fail on the views/functions/triggers DDL.

### Database Setup

| Environment | Database | Configuration |
|-------------|----------|---------------|
| **Docker Compose** | PostgreSQL 14 | Auto-provisioned, port 5433, defaults in `.env.example` |
| **Standalone Postgres** | PostgreSQL 14 | Set `LOCAL_DATABASE_URL=postgresql://user:pass@localhost:5432/aifeelnews_dev` |
| **Tests** | SQLite (in-memory) | Created on the fly via `Base.metadata.create_all` — bypasses migrations |
| **Production** | Cloud SQL | Managed via Terraform — see [Multi-Environment Strategy](docs/MULTI_ENVIRONMENT_STRATEGY.md) |

Schema migrations are managed by Alembic (17 migration files; see [docs/DATABASE.md § 2](docs/DATABASE.md#2-migrations) for the inventory):
```bash
alembic upgrade head              # Apply all pending migrations
alembic downgrade -1              # Rollback last migration
alembic history                   # View migration history
```

**Loading sample data.** A static, fully enriched seed dataset of 75 articles (50 English + 25 German) across 15 sources — with sentiment, magnitude, GCP-NL entities, and topic categories, sampled from production with PII removed — is bundled at `app/seeds/seed_data.json`. Load it after running migrations:

```bash
python -m app.seeds.seed_db                       # idempotent: safe to re-run, skips existing URLs
python -m app.seeds.seed_db --reset               # wipe seed rows then reinsert
python -m app.seeds.seed_db --dry-run             # show what would be inserted, no commits
python -m app.seeds.seed_db --queue-crawl-jobs    # also enqueue PENDING crawl_jobs for the worker
```

This is the recommended path for local development and demos — no Mediastack key required. The seed URLs are real, so `--queue-crawl-jobs` lets the worker exercise the full pipeline against live article pages (a mix of SUCCESS / RATE_LIMITED / FAILED / FORBIDDEN_BY_ROBOTS terminal states is expected behaviour, not a fault). For "production-shape" data, configure `MEDIASTACK_API_KEY` and run `python -m app.jobs.run_ingestion` instead — see the "Two run modes" section above for what that path requires.

### Environment Variables

**Backend** (`.env` — copy from `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `ENV` | No | `local` (default) / `development` / `production` |
| `LOCAL_DATABASE_URL` | When running backend on host | PostgreSQL URL pointing at a host-side instance (`postgresql://user:pass@localhost:5432/aifeelnews`). SQLite is not a supported substitute — the migration chain uses Postgres-only DDL. |
| `DATABASE_URL` | Docker | PostgreSQL URL for docker-compose (`postgresql://postgres:pass@db:5432/aifeelnews`); committed default in `.env.example` works as-is. |
| `MEDIASTACK_API_KEY` | Production-equivalent mode only | Paid tier required — the free tier is HTTP-only and the project enforces HTTPS. Demo mode skips ingestion and uses the bundled seed instead. |
| `MEDIASTACK_LANGUAGES` | No | Comma-separated ISO 639-1 codes to ingest (default `en,de` — English + German). The same sources are queried per language; German-language outlets serve the DE feed. Set to `en` for English-only. |
| `SENTIMENT_PROVIDER` | No | `VADER` (default in `.env.example`, free, no credentials) or `GCP_NL` (production-equivalent, needs a GCP service account JSON with the Cloud Natural Language API enabled). GCP NL analyzes both English and German (sentiment + entities + V2-model categories); the VADER fallback is English-only. |

**Frontend** (`frontend/.env` — copy from `frontend/.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | No | Leave unset for `npm run dev` against the docker-compose backend — `api.ts` auto-detects localhost and uses `http://127.0.0.1:8002`. Override only for a non-default backend (e.g. `http://localhost:8000` for a bare-metal `uvicorn` on port 8000) or a production build. |
| `VITE_FIREBASE_*` | For auth | 4 Firebase config values from [Firebase Console](https://console.firebase.google.com) |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /docs` | Interactive OpenAPI documentation |
| `GET /health` | Health check with DB connectivity |
| `GET /ready` | Readiness probe (DB-aware) |
| `GET /version` | Build SHA + timestamp |
| `GET /metrics` | Lightweight observability metrics |
| `GET /api/v1/articles/`, `GET /api/v1/articles/{id}`, `GET /api/v1/articles/latest` | Articles with sentiment data; list routes accept `skip`, `limit`, `sentiment_label`, `category`, `source_id`, `search`, `published_after`, `published_before`, `language` (ISO 639-1, e.g. `en`/`de`) |
| `GET /api/v1/articles/search` | Full-text search (Postgres `tsvector` + `ts_rank`): `q` (supports quoted "phrases", `or`, leading `-` to exclude), `published_after`, `published_before`, `language`. `language=de` filters to German **and** uses the German stemming config. |
| `GET /api/v1/sources/`, `POST /api/v1/sources/` | News sources (`POST` is admin-only — see [Authorization](#authentication--authorization)) |
| `GET/POST/DELETE /api/v1/bookmarks/...` | User bookmarks (auth required) |
| `GET /api/v1/sentiment/info` | Active sentiment provider |
| `GET /api/v1/entities/`, `GET /api/v1/entities/types`, `GET /api/v1/entities/{id}` | NLP entities (people, orgs, locations) |
| `GET /api/v1/analytics/*` | BigQuery analytics (trends, sources, pipeline stats); entity/category routes accept an optional `language` filter |
| `GET /api/v1/db-analytics/*` | PostgreSQL analytics — window functions, CTEs, GROUPING SETS (`/sentiment/rolling`, `/sources/ranked`, `/sentiment/breakdown`, `/entities/momentum`, `/categories/daily`); all accept an optional `language` filter (EN/DE dashboard toggle) |
| `POST /api/v1/trigger-ingestion` | Cloud Scheduler: ingest pipeline (OIDC-protected) |
| `POST /api/v1/cleanup` | Cloud Scheduler: TTL cleanup (OIDC-protected) |

> Every application router is mounted under a single `/api/v1` prefix. An earlier split (core CRUD routers unprefixed, newer routers under `/api/v1`) was unified in a coordinated backend + frontend cutover, so there is one versioned API surface and `/docs` shows it whole.

**Production:** https://aifeelnews-web-813770885946.europe-west1.run.app

## Code Quality

```bash
ruff check app/                   # Lint
ruff format app/                  # Format
mypy app/                         # Type check
pytest tests/ -v                  # Backend tests
pre-commit run --all-files        # All hooks
```

Frontend (mirrors the `frontend-check.yml` CI gate):

```bash
cd frontend
npm run check                     # Type check (svelte-check + tsc)
npm test                          # Unit tests (Vitest + Testing Library)
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
- **Role-based access control via Firebase custom claims** — a `role` claim rides in the Google-signed ID token and is read server-side; `require_admin` gates admin-only routes (`POST /api/v1/sources/`). The role is verified end-to-end by Google's token signature, so it needs no `users` table column and no second source of truth (`app/deps/auth.py`)
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
- Per-IP rate limiting via `slowapi` — 30/min on the analytics + PostgreSQL `db-analytics` routes (the heaviest window-function/CTE queries), 60/min sentiment, 60/min `/metrics`, 6/h scheduler endpoints

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
