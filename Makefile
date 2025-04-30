.PHONY: reset-db ingest pipeline

# Reset the database schema using our SQLAlchemy-based job
reset-db:
	@echo "🔄 Resetting database…"
	python -m jobs.reset_db

migrate:
	@echo "📦 Running alembic migrations…"
	@alembic upgrade head

# Fetch → normalize → ingest
ingest:
	@echo "🚀 Running full ingestion pipeline…"
	python -m jobs.run_ingestion

# One-shot: reset then ingest
pipeline: reset-db ingest
	@echo "✅ Done: DB reset and ingestion complete."