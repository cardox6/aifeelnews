#!/bin/sh
set -e

# Wait for database to be ready and run migrations
echo "Starting aiFeelNews web service..."

# Retry database migration with backoff
for i in {1..5}; do
    echo "Attempting database migration (attempt $i/5)..."
    if alembic upgrade head; then
        echo "Database migration successful!"
        break
    else
        if [ $i -eq 5 ]; then
            echo "Database migration failed after 5 attempts. Exiting."
            exit 1
        fi
        echo "Migration failed, waiting ${i}0 seconds before retry..."
        sleep $((i * 10))
    fi
done

# Start the web server
echo "Starting uvicorn server on port ${PORT:-8080}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
