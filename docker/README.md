# Docker Configuration

This directory contains all Docker-related files for the aiFeelNews application.

## Files

- **`Dockerfile.web`** - Web API service optimized for GCP Cloud Run
- **`Dockerfile.worker`** - Background crawl worker service
- **`Dockerfile.scheduler`** - Scheduled ingestion service

## Usage

### Local Development
```bash
# Build and run all services
docker-compose up -d

# Build specific service
docker-compose build web
```

### Production Deployment
```bash
# Build for production
docker-compose -f docker-compose.prod.yml build

# Test production config locally
docker-compose -f docker-compose.prod.yml up
```

## Architecture

- **Web Service**: FastAPI application with health checks for load balancers
- **Worker Service**: Background processing for web crawling and content extraction
- **Scheduler Service**: Periodic ingestion from Mediastack API

All services share the same codebase but run different entry points optimized for their specific roles.

## Image hardening

- **Base image:** `python:3.14-slim`, **pinned by digest** (`@sha256:…`) in every Dockerfile — the build is reproducible and can't drift when the `3.14-slim` tag is re-pushed.
- **Non-root runtime:** each image creates and runs as a dedicated unprivileged user (`app` / `worker` / `scheduler`), never root.
- **Slim build:** no `gcc` / `libpq-dev` / `curl` in the final image — `psycopg2-binary` ships prebuilt wheels, so no compiler toolchain is needed at runtime, shrinking the image and the attack surface.
- **Healthchecks use the Python stdlib, not `curl`:** the web image probes `/health` with `urllib`; the worker and scheduler open a `SessionLocal()` DB connection. No extra binaries installed just to health-check.

## Configuration files

- **`docker-compose.yml`** — local full stack: Postgres + web + worker + scheduler. Demo-mode defaults from `.env.example` work as-is (web on host `:8002`, db on `:5433`).
- **`docker-compose.prod.yml`** — production build target (web / worker / scheduler), used to validate the production image config locally; the live deploy builds these via Cloud Build → Artifact Registry → Cloud Run.
