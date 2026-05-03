# aiFeelNews — Infrastructure as Code (Terraform)
#
# Codifies the GCP resources that power the platform:
#   - Artifact Registry, Cloud Run (via CI/CD), Cloud SQL
#   - Cloud Scheduler, Secret Manager, BigQuery
#   - IAM (least-privilege service accounts)
#   - Cloud Monitoring (uptime, alerting, dashboards)

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- API Enablement (required before any resource can use the service) ---

locals {
  required_apis = [
    "run.googleapis.com",              # Cloud Run
    "sqladmin.googleapis.com",         # Cloud SQL Admin
    "cloudscheduler.googleapis.com",   # Cloud Scheduler
    "secretmanager.googleapis.com",    # Secret Manager
    "bigquery.googleapis.com",         # BigQuery
    "language.googleapis.com",         # Cloud Natural Language
    "artifactregistry.googleapis.com", # Artifact Registry
    "cloudresourcemanager.googleapis.com",
    "monitoring.googleapis.com", # Cloud Monitoring (uptime checks, alerting, dashboards)
    "logging.googleapis.com",    # Cloud Logging (log-based metrics)
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

# --- Artifact Registry (GCR successor — IAM per-repo, regional, vuln scanning) ---

resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "aifeelnews"
  format        = "DOCKER"
  description   = "Docker images for aiFeelNews services"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# --- Cloud SQL — Managed PostgreSQL (automated backups, Auth Proxy, 99.95% SLA) ---

resource "google_sql_database_instance" "main" {
  name             = var.cloud_sql_instance_name
  database_version = var.cloud_sql_database_version
  region           = var.region

  settings {
    tier              = var.cloud_sql_tier
    availability_type = "ZONAL" # Single zone — cost-effective for student project
    disk_autoresize   = true
    disk_size         = 10 # GB, minimum for PostgreSQL

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true    # WAL-based recovery within retention window
      start_time                     = "03:00" # 3 AM UTC — outside peak usage
    }

    ip_configuration {
      ipv4_enabled = true             # Public IP — Cloud Run connects via Cloud SQL Auth Proxy
      ssl_mode     = "ENCRYPTED_ONLY" # Reject any direct connection that doesn't use TLS
    }

    database_flags {
      name  = "max_connections"
      value = "50" # Appropriate for scale-to-zero with connection pooling
    }

    # Slow-query audit. Hot-reloadable, no restart required. 1000ms is
    # tight enough to catch missing indexes, loose enough to ignore
    # cold-start latency on the first query of a Cloud Run revision.
    database_flags {
      name  = "log_min_duration_statement"
      value = "1000"
    }
  }

  deletion_protection = true

  depends_on = [google_project_service.apis["sqladmin.googleapis.com"]]
}

resource "google_sql_database" "app" {
  name     = var.cloud_sql_database_name
  instance = google_sql_database_instance.main.name
}

# Least-privilege DB user for runtime + migrations. Password lives in
# Secret Manager (aifeelnews-db-password) only. Created out-of-band via
# `gcloud sql users create`; `terraform import` brings this resource
# under management. Password rotation is also out-of-band — the
# lifecycle.ignore_changes block prevents Terraform from drifting.
resource "google_sql_user" "aifeelnews" {
  name     = "aifeelnews"
  instance = google_sql_database_instance.main.name
  password = data.google_secret_manager_secret_version.aifeelnews_db_password.secret_data

  lifecycle {
    ignore_changes = [password]
  }
}

data "google_secret_manager_secret_version" "aifeelnews_db_password" {
  secret     = google_secret_manager_secret.aifeelnews_db_password.id
  depends_on = [google_secret_manager_secret.aifeelnews_db_password]
}

# --- Secret Manager (versioned, IAM-controlled, rotatable without redeploy) ---

resource "google_secret_manager_secret" "db_password" {
  secret_id = "db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "mediastack_api_key" {
  secret_id = "mediastack-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "gcp_nlp_key" {
  secret_id = "aifeelnews-gcp-nlp-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "firebase_sa" {
  secret_id = "firebase-service-account-json"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "aifeelnews_db_password" {
  secret_id = "aifeelnews-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret" "aifeelnews_database_url" {
  secret_id = "aifeelnews-database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

# --- Cloud Run — deployed by GitHub Actions, NOT Terraform (avoids CI/CD conflict) ---

# --- Cloud Scheduler — Managed cron (survives scale-to-zero, managed retries) ---

resource "google_cloud_scheduler_job" "ingestion" {
  name      = "aifeelnews-ingestion"
  region    = var.region
  schedule  = var.ingestion_schedule
  time_zone = var.scheduler_timezone

  http_target {
    uri         = "${var.cloud_run_url}/api/v1/trigger-ingestion"
    http_method = "POST"
  }

  retry_config {
    retry_count          = 3
    min_backoff_duration = "10s"
    max_backoff_duration = "300s"
  }

  depends_on = [google_project_service.apis["cloudscheduler.googleapis.com"]]
}

resource "google_cloud_scheduler_job" "cleanup" {
  name      = "aifeelnews-cleanup"
  region    = var.region
  schedule  = var.cleanup_schedule
  time_zone = var.scheduler_timezone

  http_target {
    uri         = "${var.cloud_run_url}/api/v1/cleanup"
    http_method = "POST"
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "600s"
  }

  depends_on = [google_project_service.apis["cloudscheduler.googleapis.com"]]
}

# --- BigQuery — OLAP warehouse (columnar, partitioned, generous free tier) ---

resource "google_bigquery_dataset" "analytics" {
  dataset_id = var.bigquery_dataset_id
  location   = var.bigquery_location

  description = "Analytics warehouse for aiFeelNews sentiment data and pipeline metrics"

  default_table_expiration_ms = null # Data retained indefinitely

  depends_on = [google_project_service.apis["bigquery.googleapis.com"]]
}

resource "google_bigquery_table" "sentiment_events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "sentiment_events"

  description = "Per-article sentiment analysis events — partitioned by ingestion date, clustered by label and source"

  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }

  clustering = ["sentiment_label", "source_name"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED", description = "Unique event identifier" },
    { name = "article_id", type = "INTEGER", mode = "REQUIRED", description = "PostgreSQL article ID" },
    { name = "article_url", type = "STRING", mode = "NULLABLE", description = "Original article URL" },
    { name = "article_title", type = "STRING", mode = "NULLABLE", description = "Article headline" },
    { name = "source_name", type = "STRING", mode = "NULLABLE", description = "News source name" },
    { name = "published_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Article publication time" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Pipeline ingestion time (partition key)" },
    { name = "sentiment_provider", type = "STRING", mode = "NULLABLE", description = "Analysis provider (GCP_NL or VADER)" },
    { name = "sentiment_model", type = "STRING", mode = "NULLABLE", description = "Model version used" },
    { name = "sentiment_score", type = "FLOAT", mode = "NULLABLE", description = "Sentiment score (-1.0 to 1.0)" },
    { name = "sentiment_magnitude", type = "FLOAT", mode = "NULLABLE", description = "Emotional intensity (0.0+)" },
    { name = "sentiment_label", type = "STRING", mode = "NULLABLE", description = "Derived label: positive, negative, neutral" },
    { name = "confidence", type = "FLOAT", mode = "NULLABLE", description = "Analysis confidence score" },
    { name = "language", type = "STRING", mode = "NULLABLE", description = "Article language code" },
    { name = "country", type = "STRING", mode = "NULLABLE", description = "Article country of origin" },
    { name = "category", type = "STRING", mode = "NULLABLE", description = "Article category" },
    { name = "content_length", type = "INTEGER", mode = "NULLABLE", description = "Content length in bytes" },
    { name = "processing_time_ms", type = "INTEGER", mode = "NULLABLE", description = "Processing duration in milliseconds" },
    { name = "extraction_method", type = "STRING", mode = "NULLABLE", description = "Content extraction method used" },
  ])
}

resource "google_bigquery_table" "ingestion_events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "ingestion_events"

  description = "Pipeline run metrics — tracks each ingestion run's duration, article counts, and success rates"

  time_partitioning {
    type  = "DAY"
    field = "started_at"
  }

  schema = jsonencode([
    { name = "run_id", type = "STRING", mode = "REQUIRED", description = "Unique pipeline run identifier" },
    { name = "started_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Pipeline start time (partition key)" },
    { name = "finished_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Pipeline completion time" },
    { name = "duration_seconds", type = "FLOAT", mode = "REQUIRED", description = "Total pipeline duration" },
    { name = "articles_fetched", type = "INTEGER", mode = "REQUIRED", description = "Articles fetched from Mediastack" },
    { name = "articles_ingested", type = "INTEGER", mode = "REQUIRED", description = "New articles stored in PostgreSQL" },
    { name = "crawl_successful", type = "INTEGER", mode = "NULLABLE", description = "Successful crawl jobs (null if crawling disabled)" },
    { name = "crawl_failed", type = "INTEGER", mode = "NULLABLE", description = "Failed crawl jobs (null if crawling disabled)" },
    { name = "include_crawling", type = "BOOLEAN", mode = "REQUIRED", description = "Whether crawling was enabled for this run" },
  ])
}

# BigQuery — Entity events (one row per article-entity pair from GCP NL)
# Flat rows instead of REPEATED fields: simpler GROUP BY without UNNEST
resource "google_bigquery_table" "entity_events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "entity_events"

  description = "Per-article entity mentions from GCP NL"

  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }

  clustering = ["entity_type", "entity_name"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED", description = "Unique event identifier" },
    { name = "article_id", type = "INTEGER", mode = "REQUIRED", description = "PostgreSQL article ID" },
    { name = "article_url", type = "STRING", mode = "NULLABLE", description = "Original article URL" },
    { name = "article_title", type = "STRING", mode = "NULLABLE", description = "Article headline" },
    { name = "source_name", type = "STRING", mode = "NULLABLE", description = "News source name" },
    { name = "published_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Article publication time" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Entity extraction time (partition key)" },
    { name = "entity_name", type = "STRING", mode = "NULLABLE", description = "Entity name (e.g., Google, London)" },
    { name = "entity_type", type = "STRING", mode = "NULLABLE", description = "Entity type (PERSON, ORGANIZATION, LOCATION, etc.)" },
    { name = "salience", type = "FLOAT", mode = "NULLABLE", description = "Entity relevance score (0.0 to 1.0)" },
    { name = "mention_count", type = "INTEGER", mode = "NULLABLE", description = "Times entity appears in article text" },
    { name = "wikipedia_url", type = "STRING", mode = "NULLABLE", description = "Wikipedia link from Knowledge Graph" },
    { name = "sentiment_label", type = "STRING", mode = "NULLABLE", description = "Article-level sentiment label" },
    { name = "sentiment_score", type = "FLOAT", mode = "NULLABLE", description = "Article-level sentiment score (-1.0 to 1.0)" },
  ])

  depends_on = [google_project_service.apis["bigquery.googleapis.com"]]
}

# BigQuery — Category events (GCP NL content classification per article)
# Distinct from Mediastack article.category — these are ML-classified taxonomy paths
resource "google_bigquery_table" "category_events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "category_events"

  description = "Per-article GCP NL content categories"

  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }

  clustering = ["category_name"]

  schema = jsonencode([
    { name = "event_id", type = "STRING", mode = "REQUIRED", description = "Unique event identifier" },
    { name = "article_id", type = "INTEGER", mode = "REQUIRED", description = "PostgreSQL article ID" },
    { name = "source_name", type = "STRING", mode = "NULLABLE", description = "News source name" },
    { name = "published_at", type = "TIMESTAMP", mode = "NULLABLE", description = "Article publication time" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Category classification time (partition key)" },
    { name = "category_name", type = "STRING", mode = "NULLABLE", description = "GCP NL taxonomy path (e.g., /News/Business)" },
    { name = "category_confidence", type = "FLOAT", mode = "NULLABLE", description = "Classification confidence (0.0 to 1.0)" },
    { name = "sentiment_label", type = "STRING", mode = "NULLABLE", description = "Article-level sentiment label" },
    { name = "sentiment_score", type = "FLOAT", mode = "NULLABLE", description = "Article-level sentiment score (-1.0 to 1.0)" },
  ])

  depends_on = [google_project_service.apis["bigquery.googleapis.com"]]
}

# --- IAM — Least-privilege (dedicated SA, not default Compute Engine editor) ---
resource "google_service_account" "cloudrun" {
  account_id   = "cloudrun-sa"
  display_name = "Cloud Run Service Account"
  description  = "Least-privilege SA for aiFeelNews Cloud Run services (web, worker, scheduler)"
}

# Role 1: Read secrets (DB password, API keys, Firebase SA)
resource "google_project_iam_member" "cloudrun_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Role 2: Connect to Cloud SQL via Cloud SQL Auth Proxy
resource "google_project_iam_member" "cloudrun_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Role 3: Call Cloud Natural Language API (sentiment + entities + categories)
resource "google_project_iam_member" "cloudrun_nl_user" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Role 4: Write data to BigQuery tables (sentiment + ingestion events)
resource "google_project_iam_member" "cloudrun_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Role 5: Run BigQuery queries (analytics dashboard endpoints)
resource "google_project_iam_member" "cloudrun_bigquery_jobuser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# GitHub Actions SA — deploys containers and Cloud Run revisions
resource "google_project_iam_member" "github_actions_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

resource "google_project_iam_member" "github_actions_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

# Allow GitHub Actions to deploy Cloud Run revisions AS the dedicated SA
resource "google_service_account_iam_member" "github_actions_act_as_cloudrun" {
  service_account_id = google_service_account.cloudrun.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.github_actions_sa_email}"
}

# github-actions-sa needs Secret Manager access to fetch DB password during deploy.
resource "google_project_iam_member" "github_actions_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

# github-actions-sa needs Cloud SQL Auth Proxy to run migrations.
resource "google_project_iam_member" "github_actions_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

# github-actions-sa needs serviceUsage for Cloud Run deploy validation.
resource "google_project_iam_member" "github_actions_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

# --- Cloud Monitoring — Uptime checks, alerting, log-based metrics (free tier) ---

locals {
  cloud_run_host = replace(var.cloud_run_url, "https://", "")
}

# Uptime check — /health (tests DB, 10s timeout for cold starts)
resource "google_monitoring_uptime_check_config" "health" {
  display_name = "aifeelnews-health-check"
  timeout      = "10s"
  period       = "300s" # Every 5 minutes from multiple global locations

  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.cloud_run_host
    }
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# Notification channel
resource "google_monitoring_notification_channel" "email" {
  display_name = "aiFeelNews Alert Email"
  type         = "email"

  labels = {
    email_address = var.notification_email
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# Log-based metrics (derived from structured JSON logs, no SDK needed)
resource "google_logging_metric" "error_count" {
  name        = "aifeelnews/error_count"
  description = "Count of ERROR-severity log entries from Cloud Run"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="aifeelnews-web"
    severity>=ERROR
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# Matches "Ingestion pipeline completed" from run_ingestion.py
resource "google_logging_metric" "ingestion_runs" {
  name        = "aifeelnews/ingestion_pipeline_runs"
  description = "Count of completed ingestion pipeline runs"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="aifeelnews-web"
    (textPayload=~"Ingestion pipeline completed" OR
     jsonPayload.message=~"Ingestion pipeline completed")
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# Matches crawl errors from crawl_worker.py
resource "google_logging_metric" "crawl_failures" {
  name        = "aifeelnews/crawl_failures"
  description = "Count of failed crawl jobs"
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="aifeelnews-web"
    (textPayload=~"error crawling" OR
     jsonPayload.message=~"error crawling" OR
     textPayload=~"Error processing crawl job" OR
     jsonPayload.message=~"Error processing crawl job")
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# Alerting policies
resource "google_monitoring_alert_policy" "uptime_failure" {
  display_name = "aiFeelNews Service Down"
  combiner     = "OR"

  conditions {
    display_name = "Health check failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.health.uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.project_id"]
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# >10 errors in 5 minutes
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "aiFeelNews High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Error log count exceeds threshold"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.error_count.name}\" AND resource.type=\"cloud_run_revision\""
      comparison      = "COMPARISON_GT"
      threshold_value = 10
      duration        = "300s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}

# Monitoring dashboard (5 Cloud Run system metrics + 3 custom log-based)
resource "google_monitoring_dashboard" "main" {
  dashboard_json = jsonencode({
    displayName = "aiFeelNews — Operations"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Cloud Run — Request Count"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"aifeelnews-web\""
                  aggregation = {
                    alignmentPeriod  = "300s"
                    perSeriesAligner = "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Cloud Run — Request Latency (p99)"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/request_latencies\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"aifeelnews-web\""
                  aggregation = {
                    alignmentPeriod  = "300s"
                    perSeriesAligner = "ALIGN_PERCENTILE_99"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Cloud Run — Instance Count (Scale-to-Zero)"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/container/instance_count\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"aifeelnews-web\""
                  aggregation = {
                    alignmentPeriod  = "300s"
                    perSeriesAligner = "ALIGN_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Cloud Run — CPU Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/container/cpu/utilizations\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"aifeelnews-web\""
                  aggregation = {
                    alignmentPeriod  = "300s"
                    perSeriesAligner = "ALIGN_PERCENTILE_99"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Cloud Run — Memory Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"run.googleapis.com/container/memory/utilizations\" AND resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"aifeelnews-web\""
                  aggregation = {
                    alignmentPeriod  = "300s"
                    perSeriesAligner = "ALIGN_PERCENTILE_99"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Application Errors (Log-Based)"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"logging.googleapis.com/user/aifeelnews/error_count\""
                  aggregation = {
                    alignmentPeriod  = "300s"
                    perSeriesAligner = "ALIGN_RATE"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Ingestion Pipeline Runs"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"logging.googleapis.com/user/aifeelnews/ingestion_pipeline_runs\""
                  aggregation = {
                    alignmentPeriod  = "3600s"
                    perSeriesAligner = "ALIGN_SUM"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Crawl Failures"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "metric.type=\"logging.googleapis.com/user/aifeelnews/crawl_failures\""
                  aggregation = {
                    alignmentPeriod  = "3600s"
                    perSeriesAligner = "ALIGN_SUM"
                  }
                }
              }
            }]
          }
        }
      ]
    }
  })

  depends_on = [google_project_service.apis["monitoring.googleapis.com"]]
}
