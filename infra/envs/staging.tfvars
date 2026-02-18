# --------------------------------------------------------------------------
# Staging environment values (demonstrates multi-env capability)
#
# Why staging exists as config but isn't deployed:
#   - Shows the architecture supports multiple environments via tfvars
#   - Deploying staging would double GCP costs (Cloud SQL alone ~$7/month)
#   - For a student project, prod-only is the right cost/value trade-off
#   - If needed, `terraform apply -var-file=envs/staging.tfvars` would
#     create an identical but isolated stack
#
# Usage: terraform plan -var-file=envs/staging.tfvars
# --------------------------------------------------------------------------

project_id  = "aifeelnews-prod"
region      = "europe-west1"
environment = "staging"

# Cloud Run — smaller limits for staging
cloud_run_service_name  = "aifeelnews-web-staging"
cloud_run_image         = "europe-west1-docker.pkg.dev/aifeelnews-prod/aifeelnews/aifeelnews-web:staging"
cloud_run_memory        = "256Mi"
cloud_run_cpu           = "1"
cloud_run_min_instances = 0
cloud_run_max_instances = 2
cloud_run_concurrency   = 40

# Cloud SQL — same tier (cheapest available)
cloud_sql_instance_name    = "aifeelnews-db-staging"
cloud_sql_tier             = "db-f1-micro"
cloud_sql_database_version = "POSTGRES_14"
cloud_sql_database_name    = "aifeelnews_staging"

# Cloud Scheduler — less frequent for staging
ingestion_schedule = "0 12 * * *"
cleanup_schedule   = "0 3 * * *"

# BigQuery — same dataset (staging uses a prefix or separate tables)
bigquery_dataset_id = "aifeelnews_staging"
bigquery_location   = "europe-west1"

# IAM — same SA (single project, different services)
github_actions_sa_email = "github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com"
