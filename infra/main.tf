# --------------------------------------------------------------------------
# aiFeelNews — Infrastructure as Code (Terraform)
#
# Codifies the existing GCP resources that power the platform:
#   - Artifact Registry (Docker images)
#   - Cloud Run (API serving)
#   - Cloud SQL (PostgreSQL)
#   - Cloud Scheduler (ingestion + cleanup cron jobs)
#   - Secret Manager (credentials)
#   - BigQuery (analytics warehouse)
#   - IAM bindings (service accounts + least-privilege roles)
#   - API enablement
#
# Why Terraform?
#   - Reproducible: anyone can recreate the full stack from these files
#   - Auditable: infrastructure changes go through code review (PRs)
#   - Multi-env ready: prod.tfvars vs staging.tfvars
#   - Drift detection: `terraform plan` shows if manual changes happened
# --------------------------------------------------------------------------

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

# ==========================================================================
# API Enablement
# Why: GCP requires explicitly enabling each API before resources can use it.
# This ensures a fresh project can be bootstrapped from scratch.
# ==========================================================================

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
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

# ==========================================================================
# Artifact Registry
# Why: GCR (gcr.io) shut down March 2025. Artifact Registry is the
# successor — same Docker workflow, better security (IAM per-repo),
# regional storage, vulnerability scanning.
# ==========================================================================

resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "aifeelnews"
  format        = "DOCKER"
  description   = "Docker images for aiFeelNews services"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# ==========================================================================
# Cloud SQL — Managed PostgreSQL
# Why Cloud SQL over self-hosted?
#   - Automated backups, patching, failover
#   - Private IP / Cloud SQL Auth Proxy for secure connections
#   - SLA-backed availability (99.95%)
#   - Frees us from DB ops so we focus on application logic
# Why PostgreSQL over Firestore/Spanner?
#   - Relational model fits our data (articles, sources, users, bookmarks)
#   - SQL expertise transfers to industry
#   - Assessment requires demonstrating relational DB skills
# ==========================================================================

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
      point_in_time_recovery_enabled = false # Cost trade-off: not needed for this project scale
      start_time                     = "03:00" # 3 AM UTC — outside peak usage
    }

    ip_configuration {
      ipv4_enabled = true # Public IP — Cloud Run connects via Cloud SQL Auth Proxy
    }

    database_flags {
      name  = "max_connections"
      value = "50" # Appropriate for scale-to-zero with connection pooling
    }
  }

  deletion_protection = true

  depends_on = [google_project_service.apis["sqladmin.googleapis.com"]]
}

resource "google_sql_database" "app" {
  name     = var.cloud_sql_database_name
  instance = google_sql_database_instance.main.name
}

# ==========================================================================
# Secret Manager
# Why Secret Manager over env vars?
#   - Secrets are versioned, auditable, and access-controlled via IAM
#   - Rotation without redeployment
#   - No secrets in code, env files, or CI/CD logs
# ==========================================================================

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

# ==========================================================================
# Cloud Run — Serverless container platform
# Why Cloud Run over GKE?
#   - Scale-to-zero: no cost when idle (critical for student budget)
#   - No cluster management overhead (no nodes, no kubectl)
#   - Built-in HTTPS, load balancing, auto-scaling
#   - Sufficient for our traffic (~3 requests/day from scheduler + user traffic)
# Why not App Engine?
#   - Cloud Run gives full Docker control (multi-stage builds, any runtime)
#   - Cloud Run supports multiple services (web, worker, scheduler)
#   - More aligned with industry container practices
# ==========================================================================

resource "google_cloud_run_v2_service" "web" {
  name     = var.cloud_run_service_name
  location = var.region

  template {
    scaling {
      min_instance_count = var.cloud_run_min_instances
      max_instance_count = var.cloud_run_max_instances
    }

    containers {
      image = var.cloud_run_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cloud_run_cpu
          memory = var.cloud_run_memory
        }
      }

      startup_probe {
        http_get {
          path = "/ready"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds = 30
      }
    }

    max_instance_request_concurrency = var.cloud_run_concurrency
    timeout                          = var.cloud_run_timeout
  }

  depends_on = [google_project_service.apis["run.googleapis.com"]]
}

# Allow unauthenticated access (public API)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ==========================================================================
# Cloud Scheduler — Managed cron jobs
# Why Cloud Scheduler over cron in a container?
#   - Survives container restarts and scale-to-zero
#   - Managed retry policies
#   - Visible in GCP Console (observability)
#   - Triggers Cloud Run via HTTP — clean separation of concerns
# ==========================================================================

resource "google_cloud_scheduler_job" "ingestion" {
  name      = "aifeelnews-ingestion"
  region    = var.region
  schedule  = var.ingestion_schedule
  time_zone = var.scheduler_timezone

  http_target {
    uri         = "${google_cloud_run_v2_service.web.uri}/api/v1/trigger-ingestion"
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
    uri         = "${google_cloud_run_v2_service.web.uri}/api/v1/cleanup"
    http_method = "POST"
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "30s"
    max_backoff_duration = "600s"
  }

  depends_on = [google_project_service.apis["cloudscheduler.googleapis.com"]]
}

# ==========================================================================
# BigQuery — Analytics data warehouse
# Why BigQuery over PostgreSQL for analytics?
#   - Separation of concerns: OLTP (PostgreSQL) vs OLAP (BigQuery)
#   - Columnar storage optimized for aggregation queries
#   - 1 TB/month free queries, 10 GB/month free storage
#   - Partitioning + clustering for efficient time-range + category queries
#   - Powers the News Analyst persona dashboards
# ==========================================================================

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

# ==========================================================================
# IAM — Least-privilege access
# Why explicit IAM over primitive roles?
#   - Principle of least privilege: each SA gets only what it needs
#   - Auditable: every permission is documented in code
#   - Reviewable: IAM changes go through PR review
# ==========================================================================

# GitHub Actions SA — deploys containers and manages Cloud Run
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

resource "google_project_iam_member" "github_actions_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

# Cloud Run default SA — reads secrets at runtime
resource "google_project_iam_member" "cloud_run_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${var.project_id}@appspot.gserviceaccount.com"
}
