#!/bin/sh
set -e

# Migrations run in CI before deployment (see .github/workflows/deploy.yml).
# This script only starts the web server.
echo "Starting aiFeelNews web service..."
echo "Starting uvicorn server on port ${PORT:-8080}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
