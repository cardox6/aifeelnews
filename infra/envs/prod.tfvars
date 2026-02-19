# --------------------------------------------------------------------------
# Production environment values
# Usage: terraform plan -var-file=envs/prod.tfvars
# --------------------------------------------------------------------------

project_id  = "aifeelnews-prod"
region      = "europe-west1"
environment = "prod"

# Cloud Run (deployed by CI/CD, only URL needed for Scheduler targets)
cloud_run_url = "https://aifeelnews-web-813770885946.europe-west1.run.app"

# Cloud SQL
cloud_sql_instance_name    = "aifeelnews-db"
cloud_sql_tier             = "db-f1-micro"
cloud_sql_database_version = "POSTGRES_14"
cloud_sql_database_name    = "aifeelnews"

# Cloud Scheduler
ingestion_schedule = "0 */8 * * *"
cleanup_schedule   = "0 2 * * *"

# BigQuery
bigquery_dataset_id = "aifeelnews"
bigquery_location   = "europe-west1"

# IAM
github_actions_sa_email = "github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com"
# cloud_run_sa_email removed — SA is now created by Terraform (cloudrun-sa)
