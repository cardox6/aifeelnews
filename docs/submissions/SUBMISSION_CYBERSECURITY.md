# Cybersecurity Submission — aiFeelNews

**Module:** SE_09 — Cybersecurity
**Author:** Matias Cardone
**Submission date:** 2026-05-04

---

## How to view this submission's exact state

This document corresponds to git tag `submission-cybersec-2026-05-04` and branch `submission-2026-05-04` on the project repository. The live URL `https://aifeelnews-front.web.app/` reflects the same state at submission time but may evolve as the project continues toward the Capstone assessment in 2-3 weeks.

**File links in this document point to the frozen `submission-2026-05-04` branch**, not to `main`. That way the source they reference doesn't drift if the project keeps moving after submission.

| Pointer | Where |
|---|---|
| Repository | https://github.com/cardox6/aifeelnews/tree/submission-2026-05-04 |
| Tag | `submission-cybersec-2026-05-04` |
| Live frontend | https://aifeelnews-front.web.app/ |
| Live API | https://aifeelnews-web-813770885946.europe-west1.run.app |
| Threat model | [docs/THREAT_MODEL.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/THREAT_MODEL.md) |
| Security measures | [docs/SECURITY_MEASURES.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md) |

---

## 1. Project identity

aiFeelNews is a news sentiment analysis platform deployed on Google Cloud (Cloud Run + Cloud SQL + Firebase Auth + Firebase Hosting). It ingests articles from Mediastack, crawls original content respecting robots.txt, runs sentiment analysis via Google Cloud Natural Language API, and serves a Svelte SPA backed by a FastAPI service. Auth uses Firebase ID tokens verified server-side; the Cloud Scheduler integration uses OIDC.

The repository is **public** at https://github.com/cardox6/aifeelnews — no invitation needed.

**Team contribution:** solo project. All commits on the `submission-2026-05-04` branch are mine.

---

## 2. Documentation pointers

The two primary security artifacts:

- [docs/THREAT_MODEL.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/THREAT_MODEL.md) — STRIDE applied per component (6 components: Cloud Run web service, Cloud SQL, Firebase Auth, Cloud Scheduler → API, CI/CD, external ingestion). Trust-boundary diagram. Consolidated known-gaps list with engineering tradeoffs.
- [docs/SECURITY_MEASURES.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md) — 38 implemented controls catalogued by 8 layers (Identity & Access, Secrets, Transport & Network, Application, Data Protection, Container & Runtime, CI/CD & Supply Chain, Monitoring & Detection). Every measure is line-anchored to source.

The README's [§ Security section](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/README.md#security) gives a one-screen summary of the same material.

---

## 3. Threat model — sample inline

The full STRIDE-per-component analysis is in [THREAT_MODEL.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/THREAT_MODEL.md). Two excerpts to illustrate the level of analysis the document carries:

### Trust boundaries (ASCII diagram from the doc)

```
     ┌────────────────────────────────────────────────────────────────┐
     │                    Public internet (untrusted)                 │
     │                                                                │
     │   Browser ──HTTPS──► Firebase Hosting (SPA)                    │
     │   Browser ──HTTPS──► Cloud Run web (FastAPI)                   │
     │   Mediastack/news sites ──HTTPS──► Cloud Run worker            │
     └───────────────┬─────────────────────────────┬──────────────────┘
                     │                             │
              [TLS terminus]                  [TLS terminus]
                     │                             │
     ┌───────────────▼─────────────────────────────▼──────────────────┐
     │            GCP project boundary (aifeelnews-prod)              │
     │                                                                │
     │   Cloud Run ───Unix socket───► Cloud SQL Auth Proxy            │
     │              ───Secret Manager──► (mediastack key, db url, …)  │
     │              ───OIDC───► Cloud Scheduler                       │
     │   Firebase Auth ──ID token──► Cloud Run (verified server-side) │
     └────────────────────────────────────────────────────────────────┘
```

### Component 1 — Cloud Run web service (sample STRIDE)

| Threat | Concretely | Mitigation |
|---|---|---|
| **S**poofing | Forged Firebase ID tokens, impersonation of Cloud Scheduler | Server-side verification of every Firebase token via `firebase_admin.auth.verify_id_token` ([app/deps/auth.py:13-43](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/app/deps/auth.py#L13-L43)); OIDC verification of Scheduler audience claim ([app/deps/oidc.py](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/app/deps/oidc.py)) gated on `ENV=production` |
| **T**ampering | Modified articles, bookmark IDs in URLs | Pydantic-validated request models reject malformed input with 422; ORM-level FK + ownership checks on bookmark delete |
| **R**epudiation | "I didn't bookmark that" | Append-only `bookmarks` table with `created_at`; structured JSON logs in production retain user_id + action + timestamp |
| **I**nformation disclosure | Leaking other users' bookmarks; verbose error stack traces | Bookmark routes scope to `current_user.id` server-side; production responses use generic 503 strings (full traceback in Cloud Logging only) |
| **D**enial of service | Unauthenticated request floods | slowapi rate limiting on hot endpoints ([app/main.py:71-95](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/app/main.py#L71-L95)); Cloud Run autoscale ceiling at 10 instances |
| **E**levation of privilege | Reaching admin scheduler endpoints as a regular user | OIDC + audience-claim verification on `/api/v1/trigger-ingestion` and `/api/v1/cleanup`; least-privilege Cloud Run service account |

The same STRIDE table is filled out for the other 5 components (Cloud SQL, Firebase Auth, Cloud Scheduler → API, CI/CD, external ingestion) in the full document.

---

## 4. Security measures — table of contents (38 measures, 8 layers)

Each entry below links into [SECURITY_MEASURES.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md) where the measure is described with a code citation.

### 1. Identity & Access (6)
- [1.1 Firebase Auth (Google Sign-In)](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#11-firebase-auth-google-sign-in)
- [1.2 Server-side Firebase ID token verification](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#12-server-side-firebase-id-token-verification)
- [1.3 OIDC verification on Scheduler endpoints](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#13-oidc-verification-on-scheduler-endpoints)
- [1.4 Least-privilege application DB user](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#14-least-privilege-application-db-user)
- [1.5 Least-privilege Cloud Run service account](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#15-least-privilege-cloud-run-service-account)
- [1.6 Firebase UID linkage on user records](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#16-firebase-uid-linkage-on-user-records)

### 2. Secrets & Key Management (5)
- 2.1 GCP Secret Manager (6 secrets)
- 2.2 `DATABASE_URL` as `secretKeyRef`
- 2.3 Cascading secret lookup
- 2.4 GitHub Secrets, build/deploy time only
- 2.5 No secrets in VCS

### 3. Transport & Network (4)
- 3.1 HTTPS-only on Cloud Run
- 3.2 Cloud SQL `ssl_mode = ENCRYPTED_ONLY`
- 3.3 CORS allowlist (no wildcard)
- 3.4 Cloud SQL via Unix socket (not TCP)

### 4. Application Layer (4)
- 4.1 Pydantic input validation
- 4.2 Parameterized SQL only
- 4.3 slowapi rate limiting
- 4.4 robots.txt + honest User-Agent

### 5. Data Protection (4)
- 5.1 Article content truncation (1024 chars) + 7-day TTL
- 5.2 No full article bodies stored
- 5.3 Minimal user PII
- 5.4 Cloud SQL automated backups + PITR

### 6. Container & Runtime (3)
- 6.1 Non-root container users
- 6.2 Distroless-leaning base images
- 6.3 Cloud Run scale-to-zero

### 7. CI/CD & Supply Chain (7)
- 7.1 Dependabot
- 7.2 pip-audit (CI)
- 7.3 gitleaks (pre-commit + CI)
- 7.4 Ruff
- 7.5 mypy
- 7.6 GCP_SA_KEY scoped to `production` GitHub environment
- 7.7 SHA-pinned third-party actions

### 8. Monitoring & Detection (4)
- 8.1 Cloud Logging
- 8.2 Cloud Monitoring dashboard
- 8.3 Auto-issue on deploy failure
- 8.4 Cloud Run revision identity check on deploy

---

## 5. Live demo readiness — proofs the assessor can verify

Commands and the response codes returned by the live deployment.

**Auth-protected endpoint returns 401 with no token:**
```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  'https://aifeelnews-web-813770885946.europe-west1.run.app/bookmarks/'
# Observed: 401
```

**OIDC-protected scheduler endpoint rejects unauthenticated POSTs.** The `-d ''` is needed because POST without a body returns 411 Length Required before the auth check runs:
```bash
curl -s -o /dev/null -X POST -d '' -w '%{http_code}\n' \
  'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/trigger-ingestion'
# Observed: 401

curl -s -o /dev/null -X POST -d '' -w '%{http_code}\n' \
  'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/cleanup'
# Observed: 401
```

**Rate limit (30/minute on analytics endpoints):**
```bash
for i in $(seq 1 40); do
  curl -s -o /dev/null -w '%{http_code} ' \
    'https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/analytics/trends?days=7'
done
# Observed: 30x 200 then 10x 429 — limit configured at app/config/security.py:42
```

**CORS preflight rejects non-allowed origin** with a 400 and no `Access-Control-Allow-Origin` header in the response (the simple GET returns 200 because CORS is enforced by the browser via the missing response header, not by the server returning an error):
```bash
curl -s -i -X OPTIONS \
  -H 'Origin: https://attacker.example.com' \
  -H 'Access-Control-Request-Method: GET' \
  'https://aifeelnews-web-813770885946.europe-west1.run.app/articles/' \
  | grep -iE 'HTTP|access-control-allow-origin'
# Observed: HTTP/1.1 400 Bad Request, no access-control-allow-origin header
```

**CI security scans:** open https://github.com/cardox6/aifeelnews/actions/workflows/security.yml — gitleaks + pip-audit run on every PR plus a weekly cron.

---

## 6. Auth demo — what's wired vs. what's documented

The submission includes:

- **Firebase Google Sign-In end-to-end**: SPA → Firebase Auth → ID token → Cloud Run server-side verification → user record auto-created/looked up by `firebase_uid`. Live and demonstrable on `https://aifeelnews-front.web.app/`.
- **OIDC enforcement on Cloud Scheduler endpoints**: `/api/v1/trigger-ingestion` and `/api/v1/cleanup` reject any caller without a valid OIDC token whose audience matches the configured value. Documented in [app/deps/oidc.py](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/app/deps/oidc.py); test coverage in [tests/test_auth_security.py](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/tests/test_auth_security.py).
- **Email/Password auth (UC-09): not implemented**. Documented as 🔲 in PERSONAS_AND_USE_CASES.md. Adding it tonight risks regressing the working Google flow; deferred to the post-submission Capstone roadmap.

---

## 7. Where to find each module-description requirement

Pointers into the codebase for the items the module description asks for. I'm leaving the level judgement to the assessor.

### Authentication and authorization

- Firebase Auth (Google Sign-In) on the SPA, server-side ID-token verification on the backend ([§ 1.1, 1.2 of SECURITY_MEASURES.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#1-identity--access))
- OIDC verification on Cloud Scheduler endpoints ([§ 1.3](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#13-oidc-verification-on-scheduler-endpoints))
- Least-privilege application DB user and Cloud Run service account ([§ 1.4, 1.5](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#14-least-privilege-application-db-user))

### Input validation and SQL safety

- Pydantic validation on every route, query params included ([§ 4.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#41-pydantic-input-validation))
- Parameterized SQL only ([§ 4.2](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#42-parameterized-sql-only))

### Transport and network security

- HTTPS-only on Cloud Run ([§ 3.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#31-https-only-on-cloud-run))
- Cloud SQL `ssl_mode = ENCRYPTED_ONLY` ([§ 3.2](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#32-cloud-sql-ssl_mode--encrypted_only))
- CORS allowlist with no wildcard ([§ 3.3](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#33-cors-allowlist-no-wildcard))
- Cloud SQL via Unix socket, not TCP ([§ 3.4](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#34-cloud-sql-via-unix-socket-not-tcp))

### Secrets management

- Secret Manager for runtime secrets ([§ 2.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#21-gcp-secret-manager-6-secrets))
- `DATABASE_URL` as `secretKeyRef` so the URL itself never appears in plaintext env on Cloud Run ([§ 2.2](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#22-database_url-as-secretkeyref))
- Cascading secret lookup that prefers Secret Manager, falls through to env vars in dev ([§ 2.3](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#23-cascading-secret-lookup))
- gitleaks pre-commit + CI to catch secrets before they land in VCS ([§ 7.3](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#73-gitleaks-secret-leak-scan))

### Container security

- Non-root container users in all three Dockerfiles ([§ 6.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#61-non-root-container-users))
- Distroless-leaning base images ([§ 6.2](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#62-distroless-leaning-base-images))

### Supply chain

- Dependabot for Python + npm + GitHub Actions ([§ 7.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#71-dependabot))
- pip-audit on every PR + weekly cron ([§ 7.2](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#72-pip-audit-cve-scan-on-pinned-deps))
- SHA-pinned third-party GitHub Actions ([§ 7.7](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#77-sha-pinned-third-party-actions))

### Data protection

- Article content truncation (1024 chars) + 7-day TTL ([§ 5.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#51-article-content-truncation-1024-chars--7-day-ttl))
- Minimal user PII stored ([§ 5.3](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#53-minimal-user-pii))
- Cloud SQL automated backups + 7-day PITR ([§ 5.4](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#54-cloud-sql-automated-backups--pitr))

### Monitoring and incident readiness

- Structured JSON logs in production ([§ 8.1](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#81-cloud-logging))
- Cloud Monitoring dashboard ([§ 8.2](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#82-cloud-monitoring-dashboard))
- Auto-issue on deploy failure + revision-identity check on every deploy ([§ 8.3, 8.4](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md#83-auto-issue-on-deploy-failure))

---

## 8. Known gaps (from the threat model, not hidden)

The threat model's [Known Gaps section](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/THREAT_MODEL.md#known-gaps-consolidated) acknowledges several items deferred with reasoned tradeoffs:

- Email/password auth (UC-09) — not implemented; would risk regressing working Google flow
- Web Application Firewall (Cloud Armor) — not provisioned; rate limiting at slowapi layer is the current control, with WAF being a future hardening step
- Per-user authorization audit log — bookmark create/delete is logged at INFO level but not into a separate audit-log table
- Container image scanning beyond pip-audit — Trivy/Snyk container scanning would catch base-image CVEs that pip-audit misses

Each gap has a stated rationale; none are the result of oversight.

---

## 9. CI/CD security pipeline

The security workflow at [.github/workflows/security.yml](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/.github/workflows/security.yml) runs on every PR and weekly on a cron:

- **gitleaks** (commit-time + CI): blocks any commit containing a high-entropy secret
- **pip-audit**: scans `requirements.txt` against the OSV vulnerability database
- **CodeQL**: GitHub's static analysis for the FastAPI codebase

The deploy workflow at [.github/workflows/deploy.yml](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/.github/workflows/deploy.yml) gates production deploys on:

- All tests passing
- A merge-policy enforcement step (only `develop` or `fix/*` can merge into `main`)
- A post-deploy revision-identity check that confirms the just-deployed Cloud Run revision is actually the one serving 100% of traffic, with automatic rollback to the previous healthy revision if verification fails

---

## 10. Documentation index

| Document | Purpose |
|----------|---------|
| [THREAT_MODEL.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/THREAT_MODEL.md) | STRIDE per component (6 components); trust-boundary diagram; consolidated known-gaps |
| [SECURITY_MEASURES.md](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/docs/SECURITY_MEASURES.md) | 38 implemented controls catalogued by 8 layers, all line-anchored to source |
| [README.md § Security](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/README.md#security) | One-screen summary of the same material |
| [tests/test_auth_security.py](https://github.com/cardox6/aifeelnews/blob/submission-2026-05-04/tests/test_auth_security.py) | Auth, OIDC, CORS, rate-limit assertions executed on every PR |
