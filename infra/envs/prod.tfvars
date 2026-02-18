# --------------------------------------------------------------------------
# Production environment values
# Usage: terraform plan -var-file=envs/prod.tfvars
# --------------------------------------------------------------------------

project_id  = "aifeelnews-prod"
region      = "europe-west1"
environment = "prod"

# Cloud Run
cloud_run_service_name  = "aifeelnews-web"
cloud_run_image         = "europe-west1-docker.pkg.dev/aifeelnews-prod/aifeelnews/aifeelnews-web:latest"
cloud_run_memory        = "512Mi"
cloud_run_cpu           = "1"
cloud_run_min_instances = 0
cloud_run_max_instances = 10
cloud_run_concurrency   = 80

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
