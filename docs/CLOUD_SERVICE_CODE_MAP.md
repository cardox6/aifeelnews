# Cloud Infrastructure — Service-to-Code Mapping

> Companion reference for the Cloud Architecture Diagram.
> Maps each cloud service to the specific source files that interact with it.

## GCP Services

| Service | Purpose | Source Files |
|---------|---------|-------------|
| **Cloud Run** | Container hosting (web API, worker, scheduler) | `app/main.py` (entrypoint, health/readiness endpoints), `docker/Dockerfile.web`, `docker/Dockerfile.worker`, `docker/Dockerfile.scheduler`, `docker/startup.sh` (migration + boot), `infra/main.tf` |
| **Cloud SQL (PostgreSQL)** | Relational database (articles, users, bookmarks, entities). App and migrations connect as the least-privilege `aifeelnews` PostgreSQL user (replaces `postgres` superuser for app traffic; superuser kept for break-glass admin). Migrations run from CI via Cloud SQL Auth Proxy on `127.0.0.1:5432`; the running Cloud Run service connects via the Unix-socket form mounted by `--add-cloudsql-instances` (`/cloudsql/<project>:<region>:aifeelnews-db`). | `app/config/database.py` (connection config + Secret Manager lookup), `app/database.py` (session factory), `app/models/*.py` (10 ORM models), `alembic/env.py` + `alembic/versions/` (17 migrations; `env.py` escapes `%` in `DATABASE_URL` for configparser), `.github/workflows/deploy.yml` (Cloud SQL Auth Proxy v2.14.1 + alembic step), `infra/main.tf` (instance, SSL, backups) |
| **Secret Manager** | Credential storage (DB credentials, API keys, Firebase SA) | `app/utils/secrets.py` (`get_secret_or_env()` cascading lookup), consumed by `app/config/database.py`, `app/config/ingestion.py`, `app/utils/gcp_nlp.py`, `infra/main.tf`. Six secrets: `db-password` (postgres superuser, kept for admin), `mediastack-api-key`, `aifeelnews-gcp-nlp-key`, `firebase-service-account-json`, `aifeelnews-db-password` **NEW** (least-privilege DB user), `aifeelnews-database-url` **NEW** (Cloud Run `DATABASE_URL` ref) |
| **Cloud Natural Language API** | Sentiment analysis, entity extraction, content classification — **English + German** (categories use the V2 classification model, which supports both; the VADER fallback is English-only) | `app/utils/gcp_nlp.py` (`GcpNlpClient.annotate_text(text, language)`, V2 model), `app/utils/sentiment.py` (provider router: GCP_NL primary, VADER fallback for English only), `app/config/sentiment.py` (thresholds, project ID), `app/routers/sentiment.py` (API endpoint), `infra/main.tf` (API enablement) |
| **BigQuery** | Analytics data warehouse (sentiment trends, pipeline metrics, entity/category events) | `app/services/bigquery.py` (client, batch streaming, query functions; entity/category events carry a `language` field), `app/config/bigquery.py` (feature gate, dataset config), `app/routers/analytics.py` (trends/sources/categories/pipeline endpoints, optional `language` filter), `app/jobs/run_ingestion.py` (event queuing), `infra/main.tf` (dataset, 4 tables with schemas: sentiment / ingestion / entity / category events) |
| **Cloud Scheduler** | Cron triggers (ingestion every 8h, cleanup daily 2 AM) | `app/config/scheduler.py` (job names, schedules), `app/main.py` (`/api/v1/trigger-ingestion`, `/api/v1/cleanup` endpoints), `app/jobs/run_ingestion.py` (pipeline orchestration), `app/utils/cleanup.py` (TTL expiry), `infra/main.tf` (2 scheduler jobs) |
| **Cloud Logging** | Structured JSON log ingestion and log-based metrics | `app/utils/logging.py` (`CloudJsonFormatter`, `setup_logging()`), `app/main.py` (logging init at startup), `infra/main.tf` (3 log-based metrics: errors, ingestion runs, crawl failures) |
| **Cloud Monitoring** | Uptime checks, alerting policies, operations dashboard | `infra/main.tf` (uptime check, email notification channel, 2 alert policies, 6-widget dashboard), `app/main.py` (`/health`, `/ready`, `/version`, `/metrics` endpoints) |
| **Artifact Registry** | Docker image registry (`europe-west1-docker.pkg.dev`) | `docker/Dockerfile.web`, `docker/Dockerfile.worker`, `docker/Dockerfile.scheduler`, `.github/workflows/deploy.yml` (build, tag, push), `infra/main.tf` (repository resource) |
| **IAM & Service Accounts** | Least-privilege access control | `infra/main.tf` (`github-actions-sa`: `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser` (acts as `cloudrun-sa`), `secretmanager.secretAccessor`, `cloudsql.client`, `serviceusage.serviceUsageConsumer`[^1]; `cloudrun-sa`: `secretAccessor`, `sql.client`, `bq.dataEditor`, `bq.jobUser`) |

[^1]: `roles/storage.admin` is also bound to `github-actions-sa` in live IAM but is not codified in `infra/main.tf` — separate follow-up to reconcile.

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
| **Mediastack API** | News article metadata ingestion (English + German) | `app/config/ingestion.py` (API URL, key via Secret Manager, `MEDIASTACK_LANGUAGES=en,de`), `app/jobs/fetch_from_mediastack.py` (fetch logic; per-language + historical `date` kwargs), `app/jobs/sources_list.py` (EN + DE source definitions), `app/jobs/run_ingestion.py` (pipeline step), `app/jobs/backfill_german.py` (one-time historical German ingest) |
| **Web Crawling** | Original article content extraction (robots.txt compliant) | `app/utils/robots.py` (robots.txt parser, compliance checks), `app/config/crawler.py` (user-agent, delays, concurrency), `app/jobs/crawl_worker.py` (extraction + sentiment pipeline), `app/models/crawl_job.py` (job status tracking) |
