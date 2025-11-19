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
