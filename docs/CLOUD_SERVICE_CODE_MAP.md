# Cloud Infrastructure — Service-to-Code Mapping

> Companion reference for the Cloud Architecture Diagram.
> Maps each cloud service to the specific source files that interact with it.

## GCP Services

| Service | Purpose | Source Files |
|---------|---------|-------------|
| **Cloud Run** | Container hosting (web API, worker, scheduler) | `app/main.py` (entrypoint, health/readiness endpoints), `docker/Dockerfile.web`, `docker/Dockerfile.worker`, `docker/Dockerfile.scheduler`, `docker/startup.sh` (migration + boot), `infra/main.tf` |
| **Cloud SQL (PostgreSQL)** | Relational database (articles, users, bookmarks, entities) | `app/config/database.py` (connection config + Secret Manager lookup), `app/database.py` (session factory), `app/models/*.py` (10 ORM models), `alembic/env.py` + `alembic/versions/` (8 migrations), `infra/main.tf` (instance, SSL, backups) |
| **Secret Manager** | Credential storage (DB password, API keys, Firebase SA) | `app/utils/secrets.py` (`get_secret_or_env()` cascading lookup), consumed by `app/config/database.py`, `app/config/ingestion.py`, `app/utils/gcp_nlp.py`, `infra/main.tf` (4 secrets defined) |
| **Cloud Natural Language API** | Sentiment analysis, entity extraction, content classification | `app/utils/gcp_nlp.py` (`GcpNlpClient.annotate_text()`), `app/utils/sentiment.py` (provider router: GCP_NL primary, VADER fallback), `app/config/sentiment.py` (thresholds, project ID), `app/routers/sentiment.py` (API endpoint), `infra/main.tf` (API enablement) |
| **BigQuery** | Analytics data warehouse (sentiment trends, pipeline metrics) | `app/services/bigquery.py` (client, batch streaming, query functions), `app/config/bigquery.py` (feature gate, dataset config), `app/routers/analytics.py` (trends/sources/categories/pipeline endpoints), `app/jobs/run_ingestion.py` (event queuing), `infra/main.tf` (dataset, 2 tables with schemas) |
| **Cloud Scheduler** | Cron triggers (ingestion every 8h, cleanup daily 2 AM) | `app/config/scheduler.py` (job names, schedules), `app/main.py` (`/api/v1/trigger-ingestion`, `/api/v1/cleanup` endpoints), `app/jobs/run_ingestion.py` (pipeline orchestration), `app/utils/cleanup.py` (TTL expiry), `infra/main.tf` (2 scheduler jobs) |
| **Cloud Logging** | Structured JSON log ingestion and log-based metrics | `app/utils/logging.py` (`CloudJsonFormatter`, `setup_logging()`), `app/main.py` (logging init at startup), `infra/main.tf` (3 log-based metrics: errors, ingestion runs, crawl failures) |
| **Cloud Monitoring** | Uptime checks, alerting policies, operations dashboard | `infra/main.tf` (uptime check, email notification channel, 2 alert policies, 6-widget dashboard), `app/main.py` (`/health`, `/ready`, `/version`, `/metrics` endpoints) |
| **Artifact Registry** | Docker image registry (`europe-west1-docker.pkg.dev`) | `docker/Dockerfile.web`, `docker/Dockerfile.worker`, `docker/Dockerfile.scheduler`, `.github/workflows/deploy.yml` (build, tag, push), `infra/main.tf` (repository resource) |
| **IAM & Service Accounts** | Least-privilege access control | `infra/main.tf` (`github-actions-sa`: run.admin + ar.writer; `cloudrun-sa`: secretAccessor, sql.client, bq.dataEditor, bq.jobUser) |

## Firebase Services

| Service | Purpose | Source Files |
|---------|---------|-------------|
| **Firebase Auth** | User authentication (Google Sign-In, ID token verification) | `frontend/src/lib/firebase.ts` (client SDK init, `getIdToken()`), `app/services/firebase_admin.py` (Admin SDK init, token verification), `app/deps/auth.py` (`get_current_user()` dependency), `app/models/user.py` (`firebase_uid` field) |
| **Firebase Hosting** | Frontend CDN (Svelte SPA) | `frontend/firebase.json` (hosting config, rewrites), `frontend/.firebaserc` (project: `aifeelnews-front`), `frontend/vite.config.ts` (build config) |

## CI/CD Pipelines

| Workflow | Trigger | Pipeline | Source File |
|----------|---------|----------|------------|
| **Backend deploy** | Push to `main` | Ruff lint -> mypy -> pytest -> Docker build -> AR push -> Cloud Run deploy -> health check | `.github/workflows/deploy.yml` |
| **Frontend merge** | Push to `main` | npm build -> Firebase Hosting deploy (live) | `.github/workflows/firebase-hosting-merge.yml` |
| **Frontend PR preview** | Pull request | npm build -> Firebase Hosting deploy (preview channel) | `.github/workflows/firebase-hosting-pull-request.yml` |

## External Integrations

| Service | Purpose | Source Files |
|---------|---------|-------------|
| **Mediastack API** | News article metadata ingestion | `app/config/ingestion.py` (API URL, key via Secret Manager), `app/jobs/fetch_from_mediastack.py` (fetch logic), `app/jobs/sources_list.py` (source definitions), `app/jobs/run_ingestion.py` (pipeline step) |
| **Web Crawling** | Original article content extraction (robots.txt compliant) | `app/utils/robots.py` (robots.txt parser, compliance checks), `app/config/crawler.py` (user-agent, delays, concurrency), `app/jobs/crawl_worker.py` (extraction + sentiment pipeline), `app/models/crawl_job.py` (job status tracking) |
