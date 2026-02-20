# --------------------------------------------------------------------------
# Outputs — Expose key values after apply
# Useful for CI/CD, debugging, and documentation
# --------------------------------------------------------------------------

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name (used by Cloud SQL Auth Proxy)"
  value       = google_sql_database_instance.main.connection_name
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL for Docker pushes"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID for analytics queries"
  value       = google_bigquery_dataset.analytics.dataset_id
}

output "scheduler_ingestion_job" {
  description = "Cloud Scheduler ingestion job name"
  value       = google_cloud_scheduler_job.ingestion.name
}

output "scheduler_cleanup_job" {
  description = "Cloud Scheduler cleanup job name"
  value       = google_cloud_scheduler_job.cleanup.name
}

output "cloudrun_sa_email" {
  description = "Dedicated Cloud Run service account email (use in deploy.yml --service-account flag)"
  value       = google_service_account.cloudrun.email
}

output "monitoring_dashboard_id" {
  description = "Cloud Monitoring dashboard ID"
  value       = google_monitoring_dashboard.main.id
}

output "uptime_check_id" {
  description = "Uptime check ID for the /health endpoint"
  value       = google_monitoring_uptime_check_config.health.uptime_check_id
}
