# Threat Model — aiFeelNews

STRIDE per component. Scope is the production deployment
(`aifeelnews-prod`, `europe-west1`) and the CI/CD pipeline that ships
to it. Frontend supply-chain risk is covered via Dependabot.

See also: [SECURITY_MEASURES.md](SECURITY_MEASURES.md),
[CICD_PIPELINE.md](CICD_PIPELINE.md),
[MULTI_ENVIRONMENT_STRATEGY.md](MULTI_ENVIRONMENT_STRATEGY.md).

---

## Components covered

1. [Cloud Run web service](#1-cloud-run-web-service) — the FastAPI
   app, public HTTPS endpoint.
2. [Cloud SQL PostgreSQL](#2-cloud-sql-postgresql) — the OLTP data
   layer.
3. [Firebase Auth](#3-firebase-auth) — the identity provider for end
   users.
4. [Cloud Scheduler → API](#4-cloud-scheduler--api) — the automation
   surface (`/trigger-ingestion`, `/cleanup`).
5. [CI/CD pipeline](#5-cicd-pipeline) — GitHub Actions → Artifact
   Registry → Cloud Run.
6. [External data ingestion + crawling](#6-external-data-ingestion--crawling)
   — Mediastack pulls + outbound HTTP to news sites.

Trust-boundary diagram at the end.

---

## 1. Cloud Run web service

FastAPI in a slim Python image ([docker/Dockerfile.web](../docker/Dockerfile.web)),
non-root user, fronted by Cloud Run's managed HTTPS LB. Runs as the
least-priv `cloudrun-sa`.

| ID | Threat | Description | Mitigation | Residual |
|----|--------|-------------|------------|----------|
| 1.S1 | Spoofing | Attacker impersonates a real user to call protected endpoints (e.g. `/bookmarks`). | Firebase ID token verification on every protected route — see [app/deps/auth.py:13-43](../app/deps/auth.py#L13-L43). Tokens are signed by Firebase, audience-bound to the project. | None — Firebase rotates signing keys automatically and the SDK re-fetches on every request. |
| 1.T1 | Tampering | Attacker modifies request payloads to inject SQL or NoSQL fragments. | All DB writes/reads go through SQLAlchemy ORM with parameterized queries. BigQuery analytics use `@param` + `QueryJobConfig` ([app/services/bigquery.py](../app/services/bigquery.py)). Pydantic schemas validate every request body. | None known. SQLAlchemy `text()` with f-strings would reintroduce risk — guarded by code review. |
| 1.R1 | Repudiation | A user denies they bookmarked an article. | Cloud Logging captures every authenticated request with the Firebase UID. [app/utils/logging.py](../app/utils/logging.py) emits structured JSON in production. Logs are retained for 30 days by default. | Logs are not exported to a tamper-evident sink (BigQuery). Tradeoff: log-sink storage cost vs. forensic value at the current scale; revisit if regulatory requirements appear. |
| 1.I1 | Information disclosure | Attacker reads sensitive response data via overly permissive CORS. | CORS allowlist at [app/main.py:83-97](../app/main.py#L83-L97) (Firebase Hosting URLs + localhost dev). No wildcard. Disallowed origins get HTTP 400 with no `Access-Control-Allow-Origin`. | Allowlist is small and PR-reviewed. |
| 1.I2 | Information disclosure | Stack traces leak DB schema or internal paths to clients. | FastAPI raises `HTTPException(detail=…)` with curated messages; Starlette returns 500 with no stacktrace by default. Errors logged server-side via `setup_logging()`. | If `DEBUG` were ever enabled in prod, stack traces would leak. Guarded by config — `ENV=production` is read from Cloud Run env. |
| 1.D1 | Denial of service | Attacker spams `/api/v1/sentiment/*` to drive Cloud Run CPU to max and exhaust the monthly quota. | slowapi rate limits (60/min sentiment, 30/min analytics, 6/h scheduler) keyed on `get_remote_address` — [app/main.py:65-81](../app/main.py#L65-L81), `app/routers/analytics.py`, `app/routers/sentiment.py`. Cloud Run instance cap is `max=10`. | Per-IP limiting is bypassable via a botnet. No WAF / Cloud Armor configured — see Known Gaps. |
| 1.E1 | Elevation of privilege | A bug in the auth dep lets an unauthenticated request reach a protected handler. | `get_current_user` raises 401 before the handler runs ([app/deps/auth.py:13-31](../app/deps/auth.py#L13-L31)). | None known. mypy + ruff catch broken signatures pre-merge. |

Component 1 gaps: no WAF/Cloud Armor; no JWT replay detection (stolen
token is valid for its 1h TTL).

---

## 2. Cloud SQL PostgreSQL

Postgres 14 ([infra/main.tf:64-103](../infra/main.tf#L64-L103)). Public
IP enabled but Cloud Run reaches it through the Cloud SQL Auth Proxy
over a Unix socket; `ssl_mode = "ENCRYPTED_ONLY"` rejects plaintext.
Migrations and runtime queries run as `aifeelnews` (not `postgres`).
Password in Secret Manager; `DATABASE_URL` is a `secretKeyRef` on the
Cloud Run revision.

| ID | Threat | Description | Mitigation | Residual |
|----|--------|-------------|------------|----------|
| 2.S1 | Spoofing | Attacker connects to the DB pretending to be the application. | Connections require `cloudsql.client` IAM (granted only to `cloudrun-sa` and `github-actions-sa` — [infra/main.tf:388-393](../infra/main.tf#L388-L393) and [:443-448](../infra/main.tf#L443-L448)). Password from Secret Manager (`aifeelnews-db-password`). | None — IAM-based authentication is the trust anchor. |
| 2.T1 | Tampering | SQL injection via crafted user input. | Same mitigation as 1.T1: ORM + Pydantic + parameterized BigQuery. | None known. |
| 2.T2 | Tampering | Migration scripts write malicious schema changes. | Alembic migrations run as `aifeelnews` (NOT `postgres`), so a hijacked migration cannot create extensions or drop superuser-owned objects. `alembic/env.py` reads creds from Secret Manager via `get_secret_or_env`. | The `aifeelnews` role still has CREATE/DROP on its own schema. Mitigated by code review on all migration PRs. |
| 2.R1 | Repudiation | A row was changed but no audit trail exists. | `Article` and similar models carry `created_at` / `updated_at`; the `trg_update_source_timestamp` trigger keeps `updated_at` honest. Cloud SQL has automatic backups + PITR ([infra/main.tf:75-79](../infra/main.tf#L75-L79)). | No application-level audit log (who-did-what). Tradeoff: per-row audit infra vs. current write volume. PITR covers recovery; audit is the attribution axis and is not implemented. |
| 2.I1 | Information disclosure | Network sniffer reads SQL traffic. | Cloud SQL `ssl_mode = "ENCRYPTED_ONLY"` ([infra/main.tf:83](../infra/main.tf#L83)). Cloud Run connects via Unix socket, not TCP, eliminating the network sniff threat for the prod path. | None. |
| 2.I2 | Information disclosure | A leaked DB password gives full read access. | Password lives in Secret Manager. The runtime user (`aifeelnews`) is not a superuser; even with the password, an attacker cannot create extensions or read system catalogs of other DBs. | A password leak still gives application-data read+write. Mitigated by Secret Manager IAM (only `cloudrun-sa` and `github-actions-sa` can read). |
| 2.D1 | Denial of service | Connection-pool exhaustion driven by a bug or attack. | SQLAlchemy pool tuned with `pool_pre_ping=True` and `pool_recycle=3600` ([app/database.py:29-33](../app/database.py#L29-L33)). PostgreSQL `max_connections=50` ([infra/main.tf:86-89](../infra/main.tf#L86-L89)). `log_min_duration_statement=1000` ([infra/main.tf:94-97](../infra/main.tf#L94-L97)) flags slow queries to Cloud Logging for review. | A pathologically slow query could still saturate. No formal per-query cost budget. |
| 2.E1 | Elevation of privilege | Application user gains `postgres` superuser. | `aifeelnews` is provisioned with `LOGIN` only — no `SUPERUSER`, no `CREATEDB` ([infra/main.tf:115-123](../infra/main.tf#L115-L123)). Migrations run as `aifeelnews`. `postgres` is reserved for emergency operator access. | None known. |

Component 2 gaps: no row-level security; no query-cost killer beyond
Cloud SQL's defaults; no automated DB-vuln scan (Cloud SQL handles
patching).

---

## 3. Firebase Auth

Identity provider for end users (Google Sign-In). Frontend gets a
Firebase ID token; backend verifies it via the Admin SDK.

| ID | Threat | Description | Mitigation | Residual |
|----|--------|-------------|------------|----------|
| 3.S1 | Spoofing | Attacker forges a Firebase token. | `verify_firebase_token` calls `auth.verify_id_token` from the Admin SDK — verifies signature against Firebase's public keys, audience claim against the project, and expiry ([app/services/firebase_admin.py](../app/services/firebase_admin.py)). | Firebase signing-key compromise is Google's responsibility. |
| 3.T1 | Tampering | Attacker modifies a captured ID token. | Modification breaks the JWT signature → verification fails → 401. | None. |
| 3.R1 | Repudiation | User denies a session existed. | Firebase keeps an audit log of sign-in events. Backend additionally logs the Firebase UID on every protected request. | Frontend-only events (page views without API calls) are not logged. |
| 3.I1 | Information disclosure | A leaked Firebase service-account JSON gives admin powers. | The JSON is stored in Secret Manager (`firebase-service-account-json`) and mounted into Cloud Run via `secretKeyRef`, never written to disk in CI. `.gitignore` excludes `*-key.json`. gitleaks pre-commit + CI rejects accidental commits. | A compromised CI runner could read the secret. Mitigated by GitHub Actions OIDC (see component 5). |
| 3.D1 | Denial of service | Auth provider downtime breaks login. | None at the application layer — Firebase is the SLA provider. The API still serves anonymous endpoints when Firebase is down. | Single-provider dependency. Mitigated only by Firebase's own redundancy. |
| 3.E1 | Elevation of privilege | A regular user becomes admin. | The system has no admin role today. The only privileged capability is the OIDC-protected scheduler endpoints, and those reject anything not signed by `cloudrun-sa` regardless of Firebase claims. | If admin roles are added later, Firebase custom claims will need explicit server-side validation. |

Component 3 gaps: no email/password fallback (Google only); no MFA
enforcement.

---

## 4. Cloud Scheduler → API

Cloud Scheduler hits `/api/v1/trigger-ingestion` (every 8h) and
`/api/v1/cleanup` (daily 02:00 UTC). Both require a Google-signed
OIDC token whose audience equals the Cloud Run URL and whose `email`
claim equals the configured Cloud Run SA.

| ID | Threat | Description | Mitigation | Residual |
|----|--------|-------------|------------|----------|
| 4.S1 | Spoofing | Attacker discovers the URL and calls `/trigger-ingestion` repeatedly. | OIDC verification on both endpoints ([app/deps/oidc.py:51-131](../app/deps/oidc.py#L51-L131)). Audience must equal the Cloud Run URL; signer email must equal `cloudrun-sa@aifeelnews-prod.iam.gserviceaccount.com`. Anything else → 401. | A compromise of the signer SA still fires valid requests. Mitigated by least-priv on the SA. |
| 4.T1 | Tampering | Attacker modifies the request body. | The endpoints accept no body — POST with empty payload. Anything sent is ignored. | None. |
| 4.R1 | Repudiation | Cloud Run logs don't tie a request to a Scheduler job. | The verified OIDC claims dict (sub, email, aud) is available to the route handler. Claims are logged at debug level via `setup_logging()`. | Promotion to info-level would improve audit at the cost of log volume. Tradeoff vs. log-retention spend. |
| 4.I1 | Information disclosure | Endpoint returns DB row counts in 200 response, leaking pipeline scale. | Response is intentionally generic: `{"status": "success", "results": {...counts...}}`. Counts are aggregate, not identifying. | None — no PII surfaces in the response body. |
| 4.D1 | Denial of service | An attacker (or buggy caller) hits the endpoint thousands of times. | slowapi limits both endpoints to `6/hour` per IP ([app/config/security.py](../app/config/security.py) `rate_limit_scheduler`). Scheduler itself fires 3×/day for ingestion and 1×/day for cleanup, well within budget. | Per-IP limit applies in aggregate to legitimate Google Scheduler IPs; 6/h is well above the legitimate cadence so this is by-design. |
| 4.E1 | Elevation of privilege | An attacker triggers cleanup to delete pre-TTL articles before forensics finishes. | OIDC verification blocks the call. Cleanup is bounded by the TTL config (`config.ingestion.article_content_ttl_hours`) so it cannot be coerced into deleting fresh data. | None known. |

Component 4 gaps: no IP allowlist for Google's Scheduler ranges
(Google does not publish a stable list); no replay-detection on OIDC
tokens (default 1h TTL bounds the window).

---

## 5. CI/CD pipeline

GitHub Actions builds the Docker images and deploys to Cloud Run.
Workload Identity Federation where possible; the legacy path uses a
scoped SA JSON stored in the `production` GitHub environment.

| ID | Threat | Description | Mitigation | Residual |
|----|--------|-------------|------------|----------|
| 5.S1 | Spoofing | Attacker pushes to `main` impersonating a maintainer. | GitHub branch protection on `main` requires PR review + green CI. `develop` and `fix/*` are the only branches allowed to merge into `main` (workflow guard at [.github/workflows/deploy.yml:26-34](../.github/workflows/deploy.yml#L26-L34)). | A compromised maintainer account bypasses this. Mitigated by GitHub's 2FA enforcement. |
| 5.T1 | Tampering | Attacker injects a malicious dependency via a typosquat. | `requirements.txt` pins exact versions. Dependabot ([.github/dependabot.yml](../.github/dependabot.yml)) raises PRs for upgrades; pip-audit ([.github/workflows/security.yml](../.github/workflows/security.yml)) fails CI on any pinned dep with a known CVE. | Typosquats with no published CVE are not caught. Manual review on dependency PRs is the compensating control. |
| 5.T2 | Tampering | Attacker modifies the deploy workflow to ship malware. | All workflow changes require PR review; pre-commit checks YAML validity. `pull-requests: write` is granted only on the security workflow's gitleaks job. Workflow files are reviewed under the same branch protection as code. | None known. |
| 5.R1 | Repudiation | Who deployed what is unclear. | GitHub Actions records the actor + commit SHA on every run. Cloud Run revision names embed the SHA. Auto-issue creation on deploy failure preserves the failing run for audit. | Pre-image (the actor's local commits before push) is not recorded. |
| 5.I1 | Information disclosure | Secrets leak via workflow logs. | Secrets stored in GitHub Secrets are masked in logs. `GCP_SA_KEY` is scoped to the `production` GitHub environment, not repo-wide. gitleaks pre-commit + CI catches accidental commits of secrets to the tree. | A workflow that explicitly `echo $SECRET`s would still leak. Mitigated by review. |
| 5.D1 | Denial of service | A flapping CI run blocks deploys. | Workflow has retry/backoff on transient steps. Deploy job is idempotent — re-running publishes the same image. | A persistent CI outage blocks emergency deploys; manual `gcloud run deploy` is the documented break-glass. |
| 5.E1 | Elevation of privilege | A PR's workflow run gains write access to `main`. | `permissions: contents: read` is the default for the workflow file; PR runs from forks have no secrets and no write tokens. The deploy job runs on push to `main`/`develop` only. | Pwn requests / branch-injection are hard to fully eliminate; reviewed at merge time. |

Component 5 gaps: no SLSA attestation; no SBOM published with
releases; no SAST tool (CodeQL/Semgrep) on the Python source — Ruff
catches style and a small set of bug patterns but is not a security
scanner.

---

## 6. External data ingestion + crawling

Ingestion pulls article metadata from Mediastack; the crawl worker
fetches a subset of full bodies for sentiment analysis. All crawls
honour `robots.txt` and use the `aifeelnews-bot/1.0` User-Agent.

| ID | Threat | Description | Mitigation | Residual |
|----|--------|-------------|------------|----------|
| 6.S1 | Spoofing | A malicious server impersonates Mediastack. | All Mediastack calls go over HTTPS; certificate validation is the default. The base URL is pinned in `app/config/ingestion.py`. | DNS-level hijacking by a sufficiently capable adversary remains possible. Tradeoff: certificate pinning vs. cert-rotation operational cost. |
| 6.T1 | Tampering | A crawled site returns malicious HTML to exploit BeautifulSoup. | BeautifulSoup uses the stdlib `html.parser` — no external XML/XSLT. Content is truncated to 1024 chars before storage ([app/jobs/crawl_worker.py:221](../app/jobs/crawl_worker.py#L221)). | Stdlib parser CVEs would still apply; covered by pip-audit on releases. |
| 6.R1 | Repudiation | Source claims we crawled them after they disallowed it. | Every crawl checks `robots.txt` first via [app/utils/robots.py](../app/utils/robots.py). User-Agent is consistent and identifiable. Crawl attempts logged with URL + timestamp + outcome. | None — robots.txt compliance is documented. |
| 6.I1 | Information disclosure | Storing full article bodies creates a copyright + privacy liability. | Content truncated to 1024 chars + 7-day TTL (`config.ingestion.article_content_ttl_hours`). Cleanup runs via `/api/v1/cleanup` (OIDC-protected) and the `ttl_cleanup` background job. | None — truncation + TTL is the design. |
| 6.I2 | Information disclosure | Crawling exposes our outbound IP to news sites. | Cloud Run egress IPs rotate. Crawling runs on a separate `worker` revision and cron, uncorrelated with user-traffic egress. | Determined operators can still profile the crawler IP range over time. |
| 6.D1 | Denial of service | A slow crawl target ties up the worker. | Request timeout (`crawler_request_timeout`, default 10s). Per-domain semaphore caps concurrent requests (default 2). Exception handlers ([app/jobs/crawl_worker.py:456-494](../app/jobs/crawl_worker.py#L456-L494)) `db.rollback()` before re-committing the failure record, so a poisoned job can't trap the worker in retry. | A farm of slow targets can still degrade throughput. Cap of 100 articles/run bounds impact. |
| 6.E1 | Elevation of privilege | A crawl payload exploits a parser bug to run code in the worker. | Non-root user ([docker/Dockerfile.worker](../docker/Dockerfile.worker)); no shell entrypoint; no GCP creds beyond what Cloud Run mints. RCE would be sandboxed to the worker revision. | No seccomp profile, no read-only FS. Tradeoff: profile maintenance vs. exploit likelihood given the parser stack. |

Component 6 gaps: no per-article hash / dedup across crawl history
(re-crawl on TTL expiry is allowed); no robots.txt cache validation
across runs.

---

## Trust boundaries

```
+-------------+      HTTPS       +---------------------+      Unix socket    +-------------+
|  Browser    | ---------------> |  Cloud Run          | ------------------> |  Cloud SQL  |
|  (user)     |  Firebase ID JWT |  aifeelnews-web     |  Cloud SQL Proxy    |  Postgres   |
+-------------+                  |  cloudrun-sa        |                     +-------------+
       ^                         +---------------------+
       |                              ^         |
       |   Google Sign-In             |         | annotateText, secrets
       v                              |         v
+-------------+                  +---------------------+
|  Firebase   |                  |  GCP services       |
|  Auth       |                  |  - Cloud NL API     |
+-------------+                  |  - Secret Manager   |
                                 |  - BigQuery         |
                                 +---------------------+
                                        ^
                                        | OIDC bearer (audience-bound)
                                        |
+-----------------+              +---------------------+
| Cloud Scheduler | -----------> |  /api/v1/trigger-*  |
| cloudrun-sa     |  HTTPS+OIDC  |                     |
+-----------------+              +---------------------+

GitHub Actions (CI) ---WIF/SA-key---> Artifact Registry ---> Cloud Run revision
```

Each arrow crosses a trust boundary. Every boundary is mitigated by at
least one control in the tables above.

---

## Known gaps (consolidated)

Things that are not mitigated, with the tradeoff for each.

- **No WAF / Cloud Armor.** Per-IP slowapi rate limiting is the only
  layer-7 DoS defence. Tradeoff: Cloud Armor pricing (~$5/policy/month
  + per-request cost) vs. current request volume; revisit if abuse
  appears.
- **No SAST tool in CI** (CodeQL, Semgrep). Tradeoff: per-PR runtime
  + queue cost vs. current code-review coverage and the small bug-rule
  subset Ruff already enforces.
- **No SLSA attestation / SBOM.** Builds are reproducible (pinned
  deps), but supply-chain provenance is not signed. Tradeoff: tooling
  + verifier complexity vs. a single-team ownership model.
- **Cloud SQL `cloudsql.iam_authentication` flag not enabled.**
  Tradeoff: changing live DB auth mode after migrations stabilised
  carries rollback risk; planned for a separate maintenance window.
- **No formal pen-test / red-team history.** Dependabot + pip-audit
  + gitleaks are automated; they do not replace human review.
- **Cloud SQL HA = ZONAL** (single zone). Tradeoff: 24/7 cost
  (REGIONAL roughly doubles instance price) vs. RTO target. Daily
  backups + PITR cover the durability axis.
- **TOCTOU race in `get_or_create_source`** ([app/jobs/ingest_articles.py:9-15](../app/jobs/ingest_articles.py#L9-L15)).
  Two concurrent ingest jobs can both attempt to insert the same
  source name; the second fails on the UNIQUE constraint and rolls
  back its batch. Clean fix is `INSERT … ON CONFLICT (name) DO NOTHING
  RETURNING id` (PostgreSQL-specific). Deferred because the SQLite-based
  test suite cannot exercise the `ON CONFLICT` path; landing it
  without a Postgres-CI safety net would risk silent regressions.
  Cloud Scheduler currently runs non-overlapping ingest jobs, so the
  race window is small in practice.
- **TOCTOU semantics in `delete_bookmark`** ([app/routers/bookmarks.py:47-61](../app/routers/bookmarks.py#L47-L61)).
  Two concurrent DELETE requests both pass the existence check; the
  second commits a no-op DELETE and returns 204 instead of 404. No
  data corruption — only HTTP semantics. Fix is a `rowcount` check
  post-`db.delete()`.
- **No JWT replay-detection.** Stolen Firebase tokens are valid for
  their 1h TTL.
- **No log-sink to a tamper-evident store.** Cloud Logging retains
  for 30 days; nothing copies to BigQuery for long-term audit.
- **Worker container is not seccomp / read-only-FS hardened.**
  Defence-in-depth gap on top of the non-root user — RCE in the
  crawler would still be Cloud-Run-sandboxed but could write to the FS.

Mirror entry in [SECURITY_MEASURES.md](SECURITY_MEASURES.md) under
"Known Gaps".
