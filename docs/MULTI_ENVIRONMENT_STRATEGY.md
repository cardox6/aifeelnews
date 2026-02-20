# Multi-Environment Strategy

## Overview

aiFeelNews supports multiple deployment environments (production, staging) through **Terraform variable files** (`tfvars`). Each environment gets an identical but isolated infrastructure stack, controlled entirely by which variable file is passed to `terraform plan/apply`.

## How It Works

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

**Deploy staging:**
```bash
terraform plan  -var-file=envs/staging.tfvars
terraform apply -var-file=envs/staging.tfvars
```

## Environment Comparison

| Resource | Production | Staging |
|----------|-----------|---------|
| **Environment tag** | `prod` | `staging` |
| **Cloud SQL instance** | `aifeelnews-db` | `aifeelnews-db-staging` |
| **Database name** | `aifeelnews` | `aifeelnews_staging` |
| **Cloud SQL tier** | `db-f1-micro` | `db-f1-micro` |
| **Cloud Run URL** | `aifeelnews-web-813...run.app` | `aifeelnews-web-staging...run.app` |
| **Ingestion schedule** | Every 8 hours (`0 */8 * * *`) | Once daily at noon (`0 12 * * *`) |
| **Cleanup schedule** | Daily at 2 AM | Daily at 3 AM |
| **BigQuery dataset** | `aifeelnews` | `aifeelnews_staging` |
| **Region** | `europe-west1` | `europe-west1` |

## Why Staging Is Not Deployed

The staging configuration exists as a **design artifact** demonstrating multi-environment capability. It is not actively deployed because:

1. **Cost**: Cloud SQL alone costs ~$7-9/month (always-on, no free tier). Deploying staging would double the infrastructure cost for no production benefit.
2. **Scale**: For a student project with <10 users, a single production environment with proper CI/CD testing gates is sufficient.
3. **Risk mitigation**: The backend pipeline runs full tests (lint + type-check + unit tests) before any deployment, catching issues before they reach production.

**This is a deliberate cost/value trade-off**, not a limitation. The architecture fully supports staging activation with a single `terraform apply` command.

## Activating Staging (3 Steps)

If staging were needed (e.g., before a major release or for team testing):

```bash
# 1. Initialize Terraform for the staging workspace
cd infra
terraform workspace new staging   # or: terraform workspace select staging

# 2. Review what will be created
terraform plan -var-file=envs/staging.tfvars

# 3. Create the staging stack
terraform apply -var-file=envs/staging.tfvars
```

This creates a completely isolated Cloud SQL instance, Cloud Scheduler jobs, BigQuery dataset, and Secret Manager secrets for staging. No production resources are affected.

## CI/CD Extension Path

To enable automatic staging deployments, the GitHub Actions workflow could be extended with branch-based routing:

```yaml
# Conceptual extension (not implemented — cost trade-off)
build-and-deploy:
  if: github.ref == 'refs/heads/main'
  # → Deploy to production Cloud Run

staging-deploy:
  if: github.ref == 'refs/heads/develop'
  # → Deploy to staging Cloud Run with staging env vars
```

This pattern would enable:
- **`main` branch** → production deployment (current behavior)
- **`develop` branch** → staging deployment (future, if needed)
- **Feature branches** → tests only, no deployment

## Isolation Guarantees

Each environment is fully isolated:
- **Separate Cloud SQL instances** (different instance names, different databases)
- **Separate BigQuery datasets** (no cross-contamination of analytics data)
- **Separate Cloud Scheduler jobs** (different frequencies appropriate to environment purpose)
- **Shared IAM service accounts** (single GCP project, but services are isolated by name)
- **Same region** (`europe-west1`) to keep latency consistent and simplify networking
