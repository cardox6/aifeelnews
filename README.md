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

### Option A: Minimal Setup (SQLite + VADER)

No external services needed. Uses SQLite for the database and VADER for local sentiment analysis.

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Defaults: SQLite database, GCP_NL sentiment (change to VADER for free local analysis)
# Edit .env → SENTIMENT_PROVIDER=VADER

# Create database tables
alembic upgrade head

# Start backend API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Frontend (separate terminal)
cd frontend
cp .env.example .env              # defaults point to localhost:8000
npm install && npm run dev
```

API docs: http://localhost:8000/docs (Swagger UI). To ingest real articles, add a `MEDIASTACK_API_KEY` to `.env` ([free tier](https://mediastack.com)), then run:
```bash
python -m app.jobs.run_ingestion
```

### Option B: Full Stack (Docker Compose)

Runs PostgreSQL 14, the API server, background worker, and scheduler in containers.

```bash
cp .env.example .env
# Set in .env:
#   POSTGRES_PASSWORD=<your-password>
#   DATABASE_URL=postgresql://postgres:<your-password>@db:5432/aifeelnews
docker-compose up --build
```

This starts four services:
| Service | Port | Description |
|---------|------|-------------|
| **db** | 5433 | PostgreSQL 14 with persistent volume |
| **web** | 8080 | FastAPI API (migrations run automatically on startup) |
| **worker** | — | Background crawling + NLP analysis |
| **scheduler** | — | Periodic ingestion (every hour) |

Frontend runs separately:
```bash
cd frontend
cp .env.example .env
# Edit .env → VITE_API_BASE_URL=http://localhost:8080
npm install && npm run dev
```

### Database Setup

| Environment | Database | Configuration |
|-------------|----------|---------------|
| **Local dev** | SQLite (default) | `LOCAL_DATABASE_URL=sqlite:///./dev.db` — no install needed |
| **Docker Compose** | PostgreSQL 14 | Auto-provisioned, port 5433, set `DATABASE_URL` in `.env` |
| **Standalone Postgres** | PostgreSQL 14 | Set `LOCAL_DATABASE_URL=postgresql://user:pass@localhost:5432/aifeelnews_dev` |
| **Production** | Cloud SQL | Managed via Terraform — see [Multi-Environment Strategy](docs/MULTI_ENVIRONMENT_STRATEGY.md) |

Schema migrations are managed by Alembic (8 migration files):
```bash
alembic upgrade head              # Apply all pending migrations
alembic downgrade -1              # Rollback last migration
alembic history                   # View migration history
```

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
| `GET /api/v1/articles` | Articles with sentiment data, search, filters |
| `GET /api/v1/sources` | News sources |
| `GET /api/v1/sentiment/summary` | Sentiment aggregations |
| `GET /api/v1/entities` | NLP-extracted entities (people, orgs, locations) |
| `GET /api/v1/analytics/*` | BigQuery analytics (trends, sources, pipeline stats) |
| `GET/POST /api/v1/bookmarks` | User bookmarks (auth required) |
| `POST /api/v1/trigger-ingestion` | Cloud Scheduler: trigger pipeline |
| `POST /api/v1/cleanup` | Cloud Scheduler: TTL cleanup |

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

## Key Design Decisions

- **Scale-to-zero** Cloud Run (min=0) — zero cost when idle, cold start acceptable for news analysis
- **OLTP/OLAP separation** — PostgreSQL for API requests, BigQuery for analytics aggregations
- **Single `annotateText` call** — combines sentiment + entities + classification, 66% cost reduction vs separate calls
- **Parameterized queries only** — no f-string SQL anywhere (BigQuery uses `@param` + QueryJobConfig)
- **Data minimization** — article content truncated to 1024 chars with 7-day TTL expiry
- **robots.txt compliance** — honest `aifeelnews-bot/1.0` User-Agent, domain-based rate limiting

## Security

### Authentication & Authorization
- Firebase Auth (Google Sign-In) with server-side ID token verification (`app/deps/auth.py`)
- Protected endpoints require `Authorization: Bearer <firebase-id-token>` header
- User records created on first authenticated request, linked by Firebase UID

### Secret Management
- Production: GCP Secret Manager (`db-password`, `mediastack-api-key`, `firebase-service-account-json`)
- Cascading lookup: Secret Manager → environment variable → default (`app/utils/secrets.py`)
- No secrets in code or version control — `.env` is gitignored

### API Security
- CORS restricted to specific origins (Firebase Hosting URLs + localhost) — no wildcard
- Parameterized queries only — no f-string SQL anywhere (BigQuery uses `@param` + `QueryJobConfig`)
- Input validation via Pydantic schemas on all request/response models

### Data Protection
- Article content truncated to 1024 chars with 7-day TTL expiry (data minimization)
- `robots.txt` compliance with honest `aifeelnews-bot/1.0` User-Agent, domain-based rate limiting
- Never store full article bodies (copyright + privacy)

### Infrastructure Security
- Least-privilege IAM: `cloudrun-sa` (5 roles), `github-actions-sa` (2 roles)
- Cloud SQL: SSL/TLS enforced (`require_ssl = true` in Terraform) — rejects unencrypted connections
- Non-root container users (`app`, `worker`, `scheduler`) in all Docker images
- CI/CD secrets stored in GitHub Secrets, injected at build time only

## License

Educational/research/assessment purposes.
