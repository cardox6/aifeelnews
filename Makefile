.PHONY: reset-db ingest pipeline migrate env-init

# Create a local .env from the tracked template (only the template ships in
# the repo; there are no .env.local/.env.docker files to switch between).
env-init:
		@echo "🔧 Creating .env from .env.example…"
		cp .env.example .env
		@echo "✅ .env created. Fill in your secrets before running."

# Reset the database schema using SQLAlchemy-based job
reset-db:
		@echo "🔄 Resetting database…"
		python -m app.jobs.reset_db

migrate:
		@echo "📦 Running alembic migrations…"
		alembic upgrade head

# Fetch → normalize → ingest
ingest:
		@echo "🚀 Running full ingestion pipeline…"
		python -m app.jobs.run_ingestion

# One-shot: reset then ingest
pipeline: reset-db ingest
		@echo "✅ Done: DB reset and ingestion complete."
