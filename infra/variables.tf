# --------------------------------------------------------------------------
# Input variables for aiFeelNews infrastructure
# Values provided via envs/*.tfvars per environment
# --------------------------------------------------------------------------

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region (co-located with Cloud SQL, Cloud Run, Scheduler)"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Deployment environment (prod, staging)"
  type        = string
  validation {
    condition     = contains(["prod", "staging"], var.environment)
    error_message = "Environment must be 'prod' or 'staging'."
  }
}

# ---- Cloud Run ----
# Cloud Run service is deployed by CI/CD (deploy.yml), not Terraform.
# Only the URL is needed here for Scheduler job targets.

variable "cloud_run_url" {
  description = "Cloud Run service URL (used by Scheduler job targets)"
  type        = string
}

# ---- Cloud SQL ----

variable "cloud_sql_instance_name" {
  description = "Cloud SQL instance name"
  type        = string
}

variable "cloud_sql_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro"
}

variable "cloud_sql_database_version" {
  description = "PostgreSQL version for Cloud SQL"
  type        = string
  default     = "POSTGRES_14"
}

variable "cloud_sql_database_name" {
  description = "Name of the database within the Cloud SQL instance"
  type        = string
  default     = "aifeelnews"
}

# ---- Cloud Scheduler ----

variable "scheduler_timezone" {
  description = "Timezone for Cloud Scheduler jobs"
  type        = string
  default     = "UTC"
}

variable "ingestion_schedule" {
  description = "Cron schedule for news ingestion (default: every 8 hours)"
  type        = string
  default     = "0 */8 * * *"
}

variable "cleanup_schedule" {
  description = "Cron schedule for database cleanup (default: daily at 2 AM)"
  type        = string
  default     = "0 2 * * *"
}

# ---- BigQuery ----

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for analytics"
  type        = string
  default     = "aifeelnews"
}

variable "bigquery_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "europe-west1"
}

# ---- IAM ----

variable "github_actions_sa_email" {
  description = "Email of the GitHub Actions service account"
  type        = string
}

## cloud_run_sa_email removed — SA is now created by Terraform
## (google_service_account.cloudrun) with least-privilege roles
