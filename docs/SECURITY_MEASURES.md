# Security Measures — aiFeelNews

Implemented controls, organised by layer. Each entry cites the code
or Terraform resource and links to the threat(s) it mitigates in
[THREAT_MODEL.md](THREAT_MODEL.md).

---

## Layers

1. [Identity & Access](#1-identity--access)
2. [Secrets & Key Management](#2-secrets--key-management)
3. [Transport & Network](#3-transport--network)
4. [Application Layer](#4-application-layer)
5. [Data Protection](#5-data-protection)
6. [Container & Runtime](#6-container--runtime)
7. [CI/CD & Supply Chain](#7-cicd--supply-chain)
8. [Monitoring & Detection](#8-monitoring--detection)

---

## 1. Identity & Access

### 1.1 Firebase Auth (Google Sign-In)

End users authenticate via Google through Firebase. The frontend
(`frontend/src/lib/firebase.ts`) obtains an ID token; the backend
never receives a password because the flow is federated.

- **Code:** `app/services/firebase_admin.py`
- **Threats:** [3.S1](THREAT_MODEL.md#3-firebase-auth),
  [1.S1](THREAT_MODEL.md#1-cloud-run-web-service)

### 1.2 Server-side Firebase ID token verification

Protected routes depend on `get_current_user`, which extracts the
bearer token, verifies it via `auth.verify_id_token` (Firebase Admin
SDK), and resolves the Firebase UID to a User row. Bad signature,
wrong audience, or expired exp → 401.

- **Code:** `app/deps/auth.py:13-43`, `app/services/firebase_admin.py:25-27`
- **Threats:** [1.S1, 1.E1](THREAT_MODEL.md#1-cloud-run-web-service),
  [3.S1, 3.T1](THREAT_MODEL.md#3-firebase-auth)

### 1.3 OIDC verification on Scheduler endpoints

`/api/v1/trigger-ingestion` and `/api/v1/cleanup` require a
Google-signed OIDC token whose audience equals the Cloud Run URL and
whose `email` claim equals
`cloudrun-sa@aifeelnews-prod.iam.gserviceaccount.com`. Verification
uses `google.oauth2.id_token.verify_oauth2_token`. In non-prod ENV the
dependency bypasses with a warning so local dev and pytest work
without GCP credentials.

- **Code:** [app/deps/oidc.py:51-131](../app/deps/oidc.py#L51-L131),
  wired in [app/main.py:257-331](../app/main.py#L257-L331)
- **Config:** [app/config/security.py](../app/config/security.py) —
  `cloud_run_url`, `scheduler_service_account` (env-overridable)
- **Threats:** [4.S1, 4.E1](THREAT_MODEL.md#4-cloud-scheduler--api)

### 1.4 Least-privilege application DB user

Migrations and runtime queries connect as `aifeelnews`, a dedicated
Postgres role with `LOGIN` only — no `SUPERUSER`, no `CREATEDB`, no
extension creation. `postgres` is reserved for emergency operator
access. A SQL injection that escapes the ORM still cannot drop the
schema or read other DBs' system catalogs.

- **Code:** [infra/main.tf:115-123](../infra/main.tf#L115-L123),
  `alembic/env.py` (reads creds from Secret Manager)
- **Threats:** [2.E1, 2.T2](THREAT_MODEL.md#2-cloud-sql-postgresql)

### 1.5 Least-privilege Cloud Run service account

`cloudrun-sa` has 5 IAM roles ([infra/main.tf:374-414](../infra/main.tf#L374-L414)):
`secretmanager.secretAccessor`, `cloudsql.client`,
`serviceusage.serviceUsageConsumer` (Cloud NL API),
`bigquery.dataEditor`, `bigquery.jobUser`. No project admin, no IAM
admin, no broad storage role.

- **Code:** [infra/main.tf:374-414](../infra/main.tf#L374-L414)
- **Threats:** [1.E1](THREAT_MODEL.md#1-cloud-run-web-service),
  [4.S1](THREAT_MODEL.md#4-cloud-scheduler--api)

### 1.6 Firebase UID linkage on user records

`User` has a unique `firebase_uid` index, so an upstream email rotation
doesn't orphan bookmarks. Auto-create on first authenticated request
([app/deps/auth.py:36-41](../app/deps/auth.py#L36-L41)) keeps the DB
in sync without a separate sign-up step.

- **Code:** `app/models/user.py`
- **Threats:** [3.E1](THREAT_MODEL.md#3-firebase-auth)

### 1.7 Access control model

Authorization is a composite of four mechanisms, each matched to a distinct
trust relationship rather than a single paradigm. Read access to articles,
sources, sentiment and analytics is intentionally public — the platform's
value is open media-literacy insight, so only *mutations* and *user-private
data* are gated.

- **DAC (discretionary access control) — bookmark ownership.** Each bookmark
  row is owned by its creator; reads and deletes are scoped to
  `current_user.id` in the query predicate, so a user cannot read or delete
  another user's bookmark even with a guessed id (mismatched id → 404).
  Row-level discretion, enforced in SQL, no separate ACL table.
  ([app/routers/bookmarks.py:22,43,55](../app/routers/bookmarks.py))
- **Deny-by-default on protected routes.** Every user-private/mutating route
  declares `Depends(get_current_user)`, which raises 401 before the handler
  runs on a missing/invalid/expired token. Denial is the default; a valid
  token is the explicit grant. ([app/deps/auth.py:13-43](../app/deps/auth.py#L13-L43))
- **RBAC via Firebase custom claims.** The admin role is not a database column —
  it is a custom claim set on the Firebase user via the Admin SDK and carried
  inside the Google-signed ID token. `verify_firebase_token` returns the full
  decoded claims, so `require_admin` reads the role from the *cryptographically
  verified* token and gates `POST /sources/` (the one previously-unauthenticated
  mutation). Authorization via verified token claims — the role assignment is
  delegated to the identity provider and re-verified at the resource server on
  every request, with no server-side session to tamper with.
  ([app/deps/auth.py](../app/deps/auth.py), [app/routers/sources.py:13](../app/routers/sources.py#L13), [app/services/firebase_admin.py:36-38](../app/services/firebase_admin.py#L36-L38))
- **Machine identity via OIDC.** Scheduler endpoints are gated by a Google-signed
  OIDC token (audience + signer checks, § 1.3), a service-to-service authz plane
  distinct from the human role axis.

Beneath the application sits a **least-privilege enforcement floor** (§ 1.4 DB
role, § 1.5 Cloud Run service account): even if app-layer authz were bypassed,
the Postgres role and IAM grants bound the blast radius — policy the application
cannot widen at its own discretion.

The model is intentionally minimal: one human tier plus an admin tier reachable
only through a signed claim, plus machine OIDC. Its trust anchor is Google's
token signing — forging an admin role would require compromising Firebase's
signing key (see [3.S1](THREAT_MODEL.md#3-firebase-auth)).

- **Code:** [app/deps/auth.py](../app/deps/auth.py) (`require_admin`),
  [app/routers/sources.py:13](../app/routers/sources.py#L13),
  [app/routers/bookmarks.py:22,43,55](../app/routers/bookmarks.py)
- **Threats:** [3.E1](THREAT_MODEL.md#3-firebase-auth),
  [1.E1](THREAT_MODEL.md#1-cloud-run-web-service),
  [4.S1, 4.E1](THREAT_MODEL.md#4-cloud-scheduler--api)

---

## 2. Secrets & Key Management

### 2.1 GCP Secret Manager (6 secrets)

`db-password`, `mediastack-api-key`, `firebase-service-account-json`,
`aifeelnews-gcp-nlp-key`, `aifeelnews-db-password`,
`aifeelnews-database-url`. Cloud Run mounts them as `secretKeyRef`
on the revision spec — never written to disk in CI.

- **Config:** `infra/main.tf` (`google_secret_manager_secret`),
  Cloud Run revision env block
- **Threats:** [2.I2, 3.I1](THREAT_MODEL.md#3-firebase-auth)

### 2.2 DATABASE_URL as `secretKeyRef`

The connection string contains the password. As a literal env var it
would appear in `terraform plan` output and in revision metadata in
the GCP console. Mounted as `secretKeyRef` it stays in Secret Manager.

- **Config:** `infra/main.tf` (Cloud Run revision spec, `env` block)
- **Threats:** [2.I2](THREAT_MODEL.md#2-cloud-sql-postgresql),
  [5.I1](THREAT_MODEL.md#5-cicd-pipeline)

### 2.3 Cascading secret lookup

`get_secret_or_env(secret_name, env_var, default)` tries Secret
Manager first, then the named env var, then the default. Used
everywhere a secret is needed; nothing reaches into `os.environ`
directly for sensitive values, so the source can be swapped (e.g. in
tests) in one place.

- **Code:** `app/utils/secrets.py:113-142`
- **Threats:** [2.I2](THREAT_MODEL.md#2-cloud-sql-postgresql),
  [5.I1](THREAT_MODEL.md#5-cicd-pipeline)

### 2.4 GitHub Secrets, build/deploy time only

`GCP_SA_KEY`, `FIREBASE_SERVICE_ACCOUNT`, etc. are GitHub Secrets
exposed only to specific workflow jobs. `GCP_SA_KEY` is scoped to the
`production` GitHub environment, which requires a manual approval
before the deploy job can read it.

- **Config:** `.github/workflows/deploy.yml` (`environment.name: production` block)
- **Threats:** [5.I1, 5.E1](THREAT_MODEL.md#5-cicd-pipeline)

### 2.5 No secrets in VCS

`.env`, `*-key.json`, `*-credentials.json` are gitignored. The
gitleaks pre-commit hook ([.pre-commit-config.yaml:16-19](../.pre-commit-config.yaml#L16-L19))
scans every commit for AWS keys, GCP service-account JSON, Firebase
secrets, and high-entropy strings. The same scan runs in CI on every
PR plus a weekly Monday cron — newly disclosed scan rules apply
retroactively to historical commits.

- **Config:** [.pre-commit-config.yaml](../.pre-commit-config.yaml),
  [.github/workflows/security.yml](../.github/workflows/security.yml)
- **Threats:** [3.I1](THREAT_MODEL.md#3-firebase-auth),
  [5.I1](THREAT_MODEL.md#5-cicd-pipeline)

---

## 3. Transport & Network

### 3.1 HTTPS-only on Cloud Run

Cloud Run terminates HTTPS with a Google-managed cert. No HTTP
listener; HTTP requests redirect to HTTPS at the LB. Frontend Firebase
Hosting is also HTTPS-only.

- **Config:** Cloud Run default, Firebase Hosting default
- **Threats:** [1.I1](THREAT_MODEL.md#1-cloud-run-web-service),
  [3.T1](THREAT_MODEL.md#3-firebase-auth)

### 3.2 Cloud SQL `ssl_mode = ENCRYPTED_ONLY`

Cloud SQL rejects unencrypted connections at the listener. A
misconfigured local proxy still cannot send plaintext to the DB.

- **Config:** [infra/main.tf:81-84](../infra/main.tf#L81-L84)
- **Threats:** [2.I1](THREAT_MODEL.md#2-cloud-sql-postgresql)

### 3.3 CORS allowlist (no wildcard)

[app/main.py:83-97](../app/main.py#L83-L97) lists 4 allowed origins:
production Firebase Hosting (`web.app` + `firebaseapp.com`) and the
two Vite dev URLs. `allow_credentials=True` requires explicit
origins. Disallowed origins get HTTP 400 with no
`Access-Control-Allow-Origin`.

- **Code:** [app/main.py:83-97](../app/main.py#L83-L97)
- **Threats:** [1.I1](THREAT_MODEL.md#1-cloud-run-web-service)

### 3.4 Cloud SQL via Unix socket (not TCP)

Cloud Run's `--add-cloudsql-instances` exposes the DB as a Unix socket
inside Google's network. No TCP path from Cloud Run to Cloud SQL — a
routing misconfig cannot expose the DB on the public internet.

- **Config:** `infra/main.tf` Cloud Run revision, `cloudsql_instances`
- **Threats:** [2.S1, 2.I1](THREAT_MODEL.md#2-cloud-sql-postgresql)

---

## 4. Application Layer

### 4.1 Pydantic input validation

Request bodies are Pydantic models (`app/schemas/*.py`). Type
mismatches and missing fields produce 422 before the handler runs.
Query params use `Query(..., ge=1, le=365)` on analytics for the same
reason.

- **Code:** `app/schemas/`, `app/routers/*.py` `Query(...)`
- **Threats:** [1.T1](THREAT_MODEL.md#1-cloud-run-web-service),
  partial [2.T1](THREAT_MODEL.md#2-cloud-sql-postgresql)

### 4.2 Parameterized SQL only

ORM ops use SQLAlchemy 2.0 typed `select()` / `insert()` builders.
BigQuery uses `QueryJobConfig` with `@param` placeholders (e.g.
`get_sentiment_trends` in `app/services/bigquery.py`). f-string SQL is
forbidden in review; raw `text()` calls are reviewed individually.

- **Code:** `app/services/bigquery.py`, `app/routers/*.py`
- **Threats:** [1.T1, 2.T1](THREAT_MODEL.md#2-cloud-sql-postgresql)

### 4.3 slowapi rate limiting

Per-IP buckets via `get_remote_address`. Limits in
`app/config/security.py`, applied as decorators:

- `/api/v1/analytics/*` — 30/min (BigQuery cost)
- `/api/v1/sentiment/*` — 60/min (Cloud NL API cost + spam)
- `/api/v1/trigger-ingestion` — 6/h (Scheduler fires 3×/day)
- `/api/v1/cleanup` — 6/h (Scheduler fires 1×/day)

slowapi's default handler returns 429.

- **Code:** [app/main.py:65-81](../app/main.py#L65-L81) (setup),
  `app/routers/analytics.py`, `app/routers/sentiment.py`,
  [app/main.py:257-331](../app/main.py#L257-L331) (scheduler decorators)
- **Threats:** [1.D1](THREAT_MODEL.md#1-cloud-run-web-service),
  [4.D1](THREAT_MODEL.md#4-cloud-scheduler--api)

### 4.4 robots.txt + honest User-Agent

Each crawl fetches `/robots.txt` first via `app/utils/robots.py` and
respects `User-agent: aifeelnews-bot` and `User-agent: *`. The UA
`aifeelnews-bot/1.0` is in `config.crawler.crawler_user_agent`. A
per-domain semaphore + `crawler_default_delay` keeps us off any one
origin's neck.

- **Code:** `app/utils/robots.py`, `app/jobs/crawl_worker.py`,
  `app/config/crawler.py`
- **Threats:** [6.R1, 6.D1](THREAT_MODEL.md#6-external-data-ingestion--crawling)

---

## 5. Data Protection

### 5.1 Article content truncation (1024 chars) + 7-day TTL

`ArticleContent` stores at most 1024 chars of any article body. After
7 days (`config.ingestion.article_content_ttl_hours`, default 168) the
cleanup job deletes the row. This is the copyright + privacy boundary
— the system is an analysis pipeline, not a content archive.

- **Code:** `app/jobs/crawl_worker.py` (truncation),
  `app/utils/cleanup.py` (`full_database_cleanup`, the deployed TTL path —
  invoked by the OIDC-protected `POST /api/v1/cleanup` endpoint that Cloud
  Scheduler calls daily). `app/jobs/ttl_cleanup.py` is a standalone CLI/test
  helper, not the production cleanup path.
- **Threats:** [6.I1](THREAT_MODEL.md#6-external-data-ingestion--crawling)

### 5.2 No full article bodies stored

Title and description (Mediastack excerpts) are kept indefinitely;
the crawled body is the 1024-char truncation. Truncation is enforced
at write time, so a future DB consumer cannot surface a full body.

- **Code:** `app/jobs/crawl_worker.py` (write-side truncation)
- **Threats:** [6.I1](THREAT_MODEL.md#6-external-data-ingestion--crawling)

### 5.3 Minimal user PII

`User` stores `email`, `firebase_uid`, and a placeholder
`hashed_password` (empty — auth is federated). No name, no profile
picture, no address.

- **Code:** `app/models/user.py`, `app/deps/auth.py:36-41`
- **Threats:** [3.I1](THREAT_MODEL.md#3-firebase-auth)

### 5.4 Cloud SQL automated backups + PITR

Daily backups + 7-day point-in-time recovery. A successful DB-tamper
(e.g. via 2.T2) is recoverable to the last known-good state.

- **Config:** [infra/main.tf:75-79](../infra/main.tf#L75-L79)
  (`backup_configuration` with `point_in_time_recovery_enabled = true`)
- **Threats:** [2.T2](THREAT_MODEL.md#2-cloud-sql-postgresql) (recovery, not prevention)

---

## 6. Container & Runtime

### 6.1 Non-root container users

`Dockerfile.web`, `Dockerfile.worker`, `Dockerfile.scheduler` each
declare a dedicated user (`app`, `worker`, `scheduler`) and switch
via `USER` before the entrypoint. RCE inside the container runs as
that user, not root.

- **Code:** `docker/Dockerfile.web`, `docker/Dockerfile.worker`,
  `docker/Dockerfile.scheduler`
- **Threats:** [6.E1](THREAT_MODEL.md#6-external-data-ingestion--crawling)

### 6.2 Distroless-leaning base images

Web and worker run on `python:3.14-slim`, digest-pinned (no shell utilities
beyond `/bin/sh`). Smaller image, smaller attack surface for a foothold
inside the container.

- **Code:** `docker/Dockerfile.*` `FROM` directives
- **Threats:** [1.E1, 6.E1](THREAT_MODEL.md#6-external-data-ingestion--crawling)

### 6.3 Cloud Run scale-to-zero

`min_instances = 0` means there's no running container most of the
time. RCE blast radius is the lifetime of one instance — under 15
minutes between requests in low-traffic mode.

- **Config:** `infra/main.tf` `google_cloud_run_v2_service.web` → `template.scaling`
- **Threats:** [1.E1](THREAT_MODEL.md#1-cloud-run-web-service) (defence in depth)

---

## 7. CI/CD & Supply Chain

### 7.1 Dependabot

Active for `pip` (`requirements.txt`), `npm`
(`frontend/package.json`), and `github-actions`. Raises PRs for
security upgrades within ~24h of CVE disclosure. Recent merges
include `postcss`, `python-dotenv`, `protobufjs`.

- **Config:** `.github/dependabot.yml`
- **Threats:** [5.T1](THREAT_MODEL.md#5-cicd-pipeline)

### 7.2 pip-audit (CI)

Scans `requirements.txt` against the PyPI advisory DB on every push,
every PR to `main`/`develop`, and weekly Monday 06:00 UTC. `--strict`
fails the job on any known CVE.

- **Config:** [.github/workflows/security.yml](../.github/workflows/security.yml)
- **Threats:** [5.T1](THREAT_MODEL.md#5-cicd-pipeline) — complements
  7.1: Dependabot opens upgrade PRs, pip-audit fails CI on un-merged
  ones so the window between disclosure and fix is bounded.

### 7.3 gitleaks (pre-commit + CI)

Pre-commit hook ([.pre-commit-config.yaml](../.pre-commit-config.yaml))
catches secrets before they enter local history. CI workflow
([.github/workflows/security.yml](../.github/workflows/security.yml))
runs a full-history scan on every push/PR plus a weekly cron — a leak
that slipped through pre-commit gets caught at review time, and old
commits are re-scanned against new rules.

- **Config:** `.pre-commit-config.yaml`, `.github/workflows/security.yml`
- **Threats:** [5.I1](THREAT_MODEL.md#5-cicd-pipeline),
  [3.I1](THREAT_MODEL.md#3-firebase-auth)

### 7.4 Ruff

Style + lint + a small set of bug patterns (B-rules,
unused-imports). Runs in pre-commit and CI. Could enable S608 to
catch accidental `text()` SQL; currently relying on code review.

- **Config:** `.pre-commit-config.yaml`, `pyproject.toml`,
  `.github/workflows/deploy.yml` (test job)
- **Threats:** code-quality side-effect on
  [1.T1, 5.T2](THREAT_MODEL.md#5-cicd-pipeline)

### 7.5 mypy

Static type checking on `app/`. Runs in pre-commit and CI. Bad route
signatures (e.g. dependency wired wrong) fail the build before merge.

- **Config:** `.pre-commit-config.yaml`, `.github/workflows/deploy.yml`
- **Threats:** code-quality side-effect on
  [1.E1](THREAT_MODEL.md#1-cloud-run-web-service)

### 7.6 GCP_SA_KEY scoped to `production` GitHub environment

Deploy job credentials are not repo-wide; they live in the
`production` GitHub environment, which can require manual approval
and a protected branch. PR runs from forks cannot access this secret.

- **Config:** `.github/workflows/deploy.yml` (`environment.name: production`)
- **Threats:** [5.I1, 5.E1](THREAT_MODEL.md#5-cicd-pipeline)

### 7.7 SHA-pinned third-party actions

Deploy pins `google-github-actions/auth`, `setup-gcloud`, etc. to
SHAs/tagged majors so a tag hijack on an action repo cannot inject
malicious steps.

- **Config:** `.github/workflows/deploy.yml`
- **Threats:** [5.T2](THREAT_MODEL.md#5-cicd-pipeline)

### 7.8 CodeQL SAST

Static analysis via GitHub Advanced Security default setup (configured
in repo settings, not an in-repo workflow file). Scans Python,
JavaScript/TypeScript, and GitHub Actions on push/PR; findings surface
as Code Scanning alerts. Has caught stack-trace exposure
(`py/stack-trace-exposure`) and missing workflow `permissions`
(`actions/missing-workflow-permissions`).

- **Config:** GitHub repo → Security → Code scanning (default setup)
- **Threats:** [1.I1](THREAT_MODEL.md#1-cloud-run-web-service),
  [5.T2](THREAT_MODEL.md#5-cicd-pipeline)

### 7.9 Frontend checks (CI)

`npm run check` (`svelte-check` + `tsc`) and `npm test` (Vitest unit
tests) run on every push/PR via `frontend-check.yml`. `vite build`
strips TypeScript types without checking them, so this is the only gate
that fails CI on a frontend type error — and unlike the preview workflow
it is not skipped for Dependabot, so `typescript` / `@types/*` bumps are
verified. The Vitest suite extends the gate to behavioural regressions
in the frontend logic layer (the `api.ts` backend contract incl.
auth-error handling, sentiment mapping, bookmark store, theme
persistence), which would otherwise build and deploy cleanly.

- **Config:** [.github/workflows/frontend-check.yml](../.github/workflows/frontend-check.yml)
- **Threats:** code-quality side-effect on
  [5.T2](THREAT_MODEL.md#5-cicd-pipeline)

---

## 8. Monitoring & Detection

### 8.1 Cloud Logging

`setup_logging()` in `app/utils/logging.py` emits structured JSON in
production (Cloud Run's expected format) and plain text locally.
Errors, auth rejects, OIDC bypasses, rate-limit hits are logged at
appropriate levels.

- **Code:** `app/utils/logging.py`, called from `app/main.py:20`
- **Threats:** [1.R1, 4.R1](THREAT_MODEL.md#4-cloud-scheduler--api),
  [5.R1](THREAT_MODEL.md#5-cicd-pipeline)

### 8.2 Cloud Monitoring dashboard

Terraform provisions a dashboard: request count, latency p50/p95,
error rate, instance count, CPU, memory, DB connection count,
ingestion job freshness. Alert policies fire on deploy failure and
abnormal error rate.

- **Config:** `infra/main.tf` (`google_monitoring_dashboard`,
  `google_monitoring_alert_policy`)
- **Threats:** detection layer for
  [1.D1](THREAT_MODEL.md#1-cloud-run-web-service),
  [2.D1](THREAT_MODEL.md#2-cloud-sql-postgresql)

### 8.3 Auto-issue on deploy failure

A failing deploy opens a GitHub issue with the run URL, failing step,
and SHA. A botched deploy is never silently lost.

- **Config:** `.github/workflows/deploy.yml` (post-failure step)
- **Threats:** detection layer for
  [5.D1](THREAT_MODEL.md#5-cicd-pipeline)

### 8.4 Cloud Run revision identity check on deploy

After deploy, the workflow verifies the new revision is serving
traffic and that its SHA matches the build's. If not, rollback runs
automatically.

- **Config:** `.github/workflows/deploy.yml` (final verification step)
- **Threats:** detection layer for
  [5.T2](THREAT_MODEL.md#5-cicd-pipeline)

---

## Known Gaps

See [THREAT_MODEL.md → Known gaps](THREAT_MODEL.md#known-gaps-consolidated)
for the tradeoff on each:

- No WAF / Cloud Armor.
- No SLSA attestation / SBOM.
- Cloud SQL `cloudsql.iam_authentication` not enabled.
- No formal pen-test history.
- Cloud SQL HA = ZONAL.
- TOCTOU in `get_or_create_source` ([app/jobs/ingest_articles.py:9-15](../app/jobs/ingest_articles.py#L9-L15)).
- TOCTOU in `delete_bookmark` ([app/routers/bookmarks.py:47-61](../app/routers/bookmarks.py#L47-L61)).
- No JWT replay-detection.
- No tamper-evident log sink.
- Worker container not seccomp / read-only-FS hardened.
