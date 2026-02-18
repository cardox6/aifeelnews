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

variable "cloud_run_service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "aifeelnews-web"
}

variable "cloud_run_image" {
  description = "Docker image URI for the Cloud Run service"
  type        = string
}

variable "cloud_run_memory" {
  description = "Memory limit for Cloud Run containers"
  type        = string
  default     = "512Mi"
}

variable "cloud_run_cpu" {
  description = "CPU limit for Cloud Run containers"
  type        = string
  default     = "1"
}

variable "cloud_run_min_instances" {
  description = "Minimum number of Cloud Run instances (0 = scale to zero)"
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

variable "cloud_run_concurrency" {
  description = "Maximum concurrent requests per Cloud Run instance"
  type        = number
  default     = 80
}

variable "cloud_run_timeout" {
  description = "Request timeout in seconds"
  type        = string
  default     = "300s"
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
