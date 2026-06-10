.PHONY: reset-db ingest pipeline migrate env-init \
        demo demo-full frontend up down logs seed seed-reset pipeline-up

# --------------------------------------------------------------------------- #
# Docker demo (recommended for a clean, reproducible local run)
# --------------------------------------------------------------------------- #
# `make demo` brings up Postgres + the web API and loads the bundled enriched
# seed — a deterministic 75-article (EN + DE) dataset with sentiment, entities
# and categories, so every analytics chart populates offline. No API keys, no
# GCP project. The worker + scheduler are NOT started (they live behind the
# `pipeline` compose profile), so nothing pulls live data over the seed.
#
# `make demo` is backend-only and returns immediately (containers run detached),
# which is what backend work / CI / "just the API" want. `make demo-full` adds
# the Svelte frontend on top — it ends in `npm run dev`, a long-running
# foreground process you watch and Ctrl-C. Two targets on purpose: only the
# full-stack demo should pin the terminal.

demo: up
	@echo "⏳ Waiting for web to become healthy…"
	@for i in $$(seq 1 30); do \
		if [ "$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8002/health 2>/dev/null)" = "200" ]; then \
			echo "✅ web is up"; break; \
		fi; sleep 3; \
	done
	@echo "🌱 Seeding the demo dataset…"
	docker compose exec -T web python -m app.seeds.seed_db
	@echo "🎉 Demo ready → http://localhost:8002/docs (API) · http://localhost:8002/metrics"

# Full-stack demo: backend + seed (via `demo`), then the Svelte SPA. The
# frontend setup is idempotent — .env is created only if missing and npm install
# is a fast no-op once deps are cached. Ends in `npm run dev`, which BLOCKS in
# the foreground (the dev server you watch); Ctrl-C stops the frontend, then
# `make down` stops the backend. No credentials needed — the article feed and
# the whole Analytics dashboard read only public endpoints.
demo-full: demo frontend

# Start just the Svelte dev server (assumes the backend is already up, e.g. via
# `make demo`). api.ts auto-detects localhost → http://127.0.0.1:8002.
frontend:
	@echo "🎨 Preparing the frontend…"
	cd frontend && { [ -f .env ] || cp .env.example .env; } && npm install
	@echo "🚀 Starting the Svelte dev server → http://localhost:5173 (Ctrl-C to stop)"
	cd frontend && npm run dev

# Start only db + web (the default compose profile excludes worker/scheduler).
up:
	@echo "🐳 Starting db + web…"
	docker compose up --build -d db web

down:
	@echo "🛑 Stopping the stack (keeps the postgres volume)…"
	docker compose down

logs:
	docker compose logs -f web

# Load the bundled seed into the running web container.
seed:
	@echo "🌱 Seeding the demo dataset…"
	docker compose exec -T web python -m app.seeds.seed_db

# Wipe seed-derived rows first, then reload (idempotent full refresh).
seed-reset:
	@echo "🌱 Reseeding (reset)…"
	docker compose exec -T web python -m app.seeds.seed_db --reset

# Opt in to the live crawl/ingest pipeline (adds worker + scheduler).
# Requires a paid Mediastack key in .env to actually fetch new articles.
pipeline-up:
	@echo "🚀 Starting the full pipeline (db + web + worker + scheduler)…"
	docker compose --profile pipeline up --build -d

# --------------------------------------------------------------------------- #
# Bare-metal helpers (host Python, no Docker)
# --------------------------------------------------------------------------- #

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
