# Multi-Environment Strategy

## Overview

aiFeelNews implements environment separation through two complementary mechanisms:

1. **Terraform variable files** (`tfvars`) — infrastructure-level environment isolation (production vs staging)
2. **Git branching + Cloud Run tagged revisions** — cost-free preview environments for every PR

A dedicated staging environment is not deployed due to cost (~$7-9/month for Cloud SQL alone). Instead, the project uses **PR preview deploys** on Cloud Run as a zero-cost staging alternative.

## Branching Strategy (Simplified Git Flow)

```
feature/phase-b-db  ──┐
feature/phase-c-cyber ─┤── PR into: develop (CI tests + PR preview)
feature/phase-d-auth  ─┘
                           │
                           └── when deploy-ready: PR develop → main (production deploy)

fix/critical-bug  ────────── PR directly to main (hotfix escape hatch)
```

| Branch | Tests? | Deploys? | Target |
|--------|--------|----------|--------|
| `main` | Yes | Yes — production Cloud Run + Firebase | Production |
| `develop` | Yes | No — integration only | None |
| `feature/*` | Yes (on PR) | PR preview (Cloud Run tagged revision) | Preview URL |
| `fix/*` | Yes | Yes — direct to production (emergency) | Production |

**CI-enforced merge policy:** A CI gate in the `test` job blocks PRs from feature branches directly to `main`. Only `develop` and `fix/*` branches are allowed. This is enforced without GitHub Enterprise — purely through a workflow step that exits with an error.

## PR Preview Deploys (Zero-Cost Staging Alternative)

When a PR targets `develop`, the CI pipeline:

1. Builds a Docker image tagged `pr-<number>`
2. Deploys it to Cloud Run with `--tag=pr-<number> --no-traffic`
3. The revision gets its own URL: `pr-42---aifeelnews-web-xxxxx.run.app`
4. Posts the preview URL as a PR comment
5. Cleans up the tagged revision when the PR is closed

**Why this is free:** Cloud Run charges per request. Tagged revisions with `--no-traffic` and `min-instances=0` cost nothing when idle. They share the same Cloud SQL instance, Secret Manager secrets, and service account — no duplicate infrastructure.

**What this validates:**
- Docker image builds successfully
- Application starts and passes health checks
- Database connectivity works (same Cloud SQL)
- API endpoints respond correctly

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
2. **Scale**: For a student project with <10 users, PR previews + proper CI testing gates provide sufficient pre-production validation.
3. **Risk mitigation**: The backend pipeline runs full tests (lint + type-check + unit tests), multi-endpoint smoke tests, and automated rollback — catching issues before and after deployment.

**This is a deliberate cost/value trade-off**, not a limitation. The architecture supports staging activation with a single `terraform apply`.

## Isolation Guarantees

**Terraform environments** (if both deployed):
- Separate Cloud SQL instances (different names, different databases)
- Separate BigQuery datasets (no cross-contamination)
- Separate Cloud Scheduler jobs (different frequencies)
- Shared IAM service accounts (single GCP project, isolated by service name)
- Same region (`europe-west1`)

**PR preview revisions:**
- Isolated application code (separate Docker image tag per PR)
- Shared database (same Cloud SQL — acceptable for previews)
- No production traffic (enforced by `--no-traffic` flag)
- Automatic cleanup on PR close

## Deployment Safety Chain

```
Feature branch
  │
  ├── PR to develop
  │     ├── CI: ruff + mypy + pytest (quality gate)
  │     ├── Cloud Run PR preview (functional validation)
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
