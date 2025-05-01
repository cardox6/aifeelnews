.PHONY: reset-db ingest pipeline migrate env-local env-docker env-production

# Switch to local environment
env-local:
		@echo "🔧 Switching to LOCAL environment (.env.local)..."
		cp .env.local .env
		@echo "✅ Now using LOCAL database and settings."

# Switch to Docker environment
env-docker:
		@echo "🐳 Switching to DOCKER environment (.env.docker)..."
		cp .env.docker .env
		@echo "✅ Now using DOCKER database and settings."

# Switch to production environment
# env-production:
#		@echo "☁️  Switching to PRODUCTION environment (.env.production)..."
#		cp .env.production .env
#		@echo "✅ Now using PRODUCTION database and settings."

# Reset the database schema using SQLAlchemy-based job
reset-db:
		@echo "🔄 Resetting database…"
		python -m jobs.reset_db

migrate:
		@echo "📦 Running alembic migrations…"
		alembic upgrade head

# Fetch → normalize → ingest
ingest:
		@echo "🚀 Running full ingestion pipeline…"
		python -m jobs.run_ingestion

# One-shot: reset then ingest
pipeline: reset-db ingest
		@echo "✅ Done: DB reset and ingestion complete."