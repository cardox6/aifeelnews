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

# Cloud Run (deployed by CI/CD, only URL needed for Scheduler targets)
cloud_run_url = "https://aifeelnews-web-staging.europe-west1.run.app"

# Cloud SQL — same tier (cheapest available)
cloud_sql_instance_name    = "aifeelnews-db-staging"
cloud_sql_tier             = "db-f1-micro"
cloud_sql_database_version = "POSTGRES_14"
cloud_sql_database_name    = "aifeelnews_staging"

# Cloud Scheduler — less frequent for staging
ingestion_schedule = "0 12 * * *"
cleanup_schedule   = "0 3 * * *"

# Monitoring — required (no default); without it `terraform apply` halts asking
# for the value, so the documented staging apply could not actually run.
notification_email = "matias.cardone@code.berlin"

# Staging runs ingestion once daily, so the stale-data alarm must tolerate a
# ~24h gap (default 32400s = 9h would false-alarm against the daily cadence).
ingestion_stale_threshold_seconds = 93600

# BigQuery — same dataset (staging uses a prefix or separate tables)
bigquery_dataset_id = "aifeelnews_staging"
bigquery_location   = "europe-west1"

# IAM — same SA (single project, different services)
github_actions_sa_email = "github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com"
# cloud_run_sa_email removed — SA is now created by Terraform (cloudrun-sa)
