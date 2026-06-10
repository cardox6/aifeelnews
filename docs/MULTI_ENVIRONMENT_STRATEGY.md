# Multi-Environment Strategy

## Overview

aiFeelNews implements environment separation through two complementary mechanisms:

1. **Terraform variable files** (`tfvars`) — infrastructure-level environment isolation (production vs staging)
2. **Git branching + CI quality gates + Firebase Hosting PR previews** — pre-production validation on every PR

A dedicated staging environment is not deployed due to cost (~$7-9/month for Cloud SQL alone). Pre-merge validation comes from the CI gates (backend: ruff + mypy + pytest incl. a real-Postgres job; frontend: svelte-check + tsc + Vitest) plus Firebase Hosting preview channels for frontend changes. A Cloud Run PR-preview mechanism was implemented, found unworkable without dedicated preview infrastructure, and deliberately removed — see [Cloud Run PR Previews (Removed by Design)](#cloud-run-pr-previews-removed-by-design).

## Branching Strategy (Simplified Git Flow)

```
feature/phase-b-db  ──┐
feature/phase-c-cyber ─┤── PR into: develop (CI tests + frontend preview)
feature/phase-d-auth  ─┘
                           │
                           └── when deploy-ready: PR develop → main (production deploy)

fix/critical-bug  ────────── PR directly to main (hotfix escape hatch)
```

| Branch | Tests? | Deploys? | Target |
|--------|--------|----------|--------|
| `main` | Yes | Yes — production Cloud Run + Firebase | Production |
| `develop` | Yes | No — integration only | None |
| `feature/*` | Yes (on PR) | Frontend only — Firebase Hosting preview channel (PRs touching `frontend/`) | Preview URL (frontend) |
| `fix/*` | Yes | Yes — direct to production (emergency) | Production |

**CI-enforced merge policy:** A CI gate in the `test` job blocks PRs from feature branches directly to `main`. Only `develop` and `fix/*` branches are allowed. This is enforced without GitHub Enterprise — purely through a workflow step that exits with an error.

## Cloud Run PR Previews (Removed by Design)

A zero-cost backend preview-per-PR mechanism was implemented in the deployment-hardening pass (PR #28, 2026-03-17): build an image tagged `pr-<number>`, deploy it with `--tag --no-traffic` (tagged revisions with `min-instances=0` cost nothing when idle), post the revision URL as a PR comment, clean up on PR close.

It was **removed on 2026-04-29** (commit `e2bfd77`) after failing on every PR since introduction. Beyond a wrong `gcloud` flag, the design had an unfixable flaw at this project's scale: the preview revision needs a database, and both options were unacceptable —

1. **Pass the production `DATABASE_URL`** — a security risk: PR-tagged revisions are publicly reachable, so un-reviewed code could mutate production data.
2. **Stand up a separate preview Cloud SQL** — duplicate always-on infrastructure cost, defeating the "zero-cost" premise.

The jobs were deleted rather than left half-working. Pre-merge validation is covered instead by:

- **Backend:** ruff + mypy + pytest on every PR (`deploy.yml` test job), including the views/functions/triggers exercised against a real Postgres service container
- **Frontend:** svelte-check + tsc + Vitest unit tests (`frontend-check.yml`), plus a **Firebase Hosting preview channel** for every frontend-touching PR (`firebase-hosting-pull-request.yml`); the preview build points at the production API
- **Post-deploy:** multi-endpoint smoke tests with automated traffic rollback (production deploys only happen on push to `main`)

## Terraform Multi-Environment Support

All infrastructure is defined once in `infra/main.tf`. Environment-specific values live in separate files:

```
infra/
├── main.tf              # Resource definitions (shared)
├── variables.tf         # Input variable declarations
├── outputs.tf           # Output values
└── envs/
    ├── prod.tfvars      # Production values (active)
    └── staging.tfvars   # Staging values (ready to activate)
```

**Deploy production:**
```bash
terraform plan  -var-file=envs/prod.tfvars
terraform apply -var-file=envs/prod.tfvars
```

**Deploy staging (if needed):**
```bash
terraform workspace new staging
terraform plan  -var-file=envs/staging.tfvars
terraform apply -var-file=envs/staging.tfvars
```

### Environment Comparison

| Resource | Production | Staging (not deployed) |
|----------|-----------|---------|
| **Environment tag** | `prod` | `staging` |
| **Cloud SQL instance** | `aifeelnews-db` | `aifeelnews-db-staging` |
| **Database name** | `aifeelnews` | `aifeelnews_staging` |
| **Cloud SQL tier** | `db-f1-micro` | `db-f1-micro` |
| **Ingestion schedule** | Every 8 hours (`0 */8 * * *`) | Once daily at noon (`0 12 * * *`) |
| **Cleanup schedule** | Daily at 2 AM | Daily at 3 AM |
| **BigQuery dataset** | `aifeelnews` | `aifeelnews_staging` |
| **Region** | `europe-west1` | `europe-west1` |

## Why Staging Is Not Deployed

The staging configuration exists as a **design artifact** demonstrating multi-environment capability. It is not actively deployed because:

1. **Cost**: Cloud SQL alone costs ~$7-9/month (always-on, no free tier). Deploying staging would double the infrastructure cost with no production benefit.
2. **Scale**: For a student project with <10 users, the CI quality gates (backend tests incl. real Postgres, frontend type-check + unit tests) and Firebase frontend previews provide sufficient pre-production validation.
3. **Risk mitigation**: The backend pipeline runs full tests (lint + type-check + unit tests), multi-endpoint smoke tests, and automated rollback — catching issues before and after deployment.

**This is a deliberate cost/value trade-off**, not a limitation. The architecture supports staging activation with a single `terraform apply`.

## Isolation Guarantees

**Terraform environments** (if both deployed):
- Separate Cloud SQL instances (different names, different databases)
- Separate BigQuery datasets (no cross-contamination)
- Separate Cloud Scheduler jobs (different frequencies)
- Shared IAM service accounts (single GCP project, isolated by service name)
- Same region (`europe-west1`)

**Firebase Hosting PR previews:**
- Isolated, auto-expiring preview channel per frontend-touching PR
- Frontend only — backend changes are validated by CI tests, not a preview deploy (see [Cloud Run PR Previews (Removed by Design)](#cloud-run-pr-previews-removed-by-design))
- The preview build points at the production API; no per-PR backend exists

## Deployment Safety Chain

```
Feature branch
  │
  ├── PR to develop
  │     ├── CI: ruff + mypy + pytest (backend quality gate)
  │     ├── CI: svelte-check + tsc + vitest (frontend quality gate)
  │     └── Firebase Hosting preview (frontend validation)
  │
  ├── Merged to develop (batched with other features)
  │
  └── PR develop → main (release)
        ├── CI tests re-run
        ├── Alembic migrations run in CI (before deploy)
        ├── Docker image built and pushed
        ├── Cloud Run deploy
        ├── Multi-endpoint smoke tests (/health, /version, /metrics, /articles)
        ├── Automated rollback on failure
        └── Deployment notification (GitHub Environment + job summary + failure issue)
```
