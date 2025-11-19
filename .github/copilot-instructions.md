## aiFeelNews — Copilot & contributor instructions

Target audience: GitHub Copilot / AI agents and new contributors. This file explains the repo architecture, university assessment constraints (Relational DB, Cybersecurity, Cloud/CICD) and hard rules Copilot must follow.

Core idea: ingest Mediastack metadata, politely crawl original articles, extract main text, run sentiment with Google Cloud Natural Language (GCP NL), and persist minimal metadata + sentiment indicators. Full article bodies must NOT be stored long-term; only truncated snippets with TTL are allowed.

Essential references (quick):
- FastAPI app entry: `app/main.py` (routers + model imports for SQLAlchemy metadata).
- DB config: `app/config.py` (pydantic settings) and `app/database.py` (engine, SessionLocal).
- Ingestion pipeline: `app/jobs/fetch_from_mediastack.py`, `app/jobs/normalize_articles.py`, `app/jobs/ingest_articles.py`, `app/jobs/run_ingestion.py`.
- Sentiment: `app/utils/sentiment.py` (currently VADER); production uses a GCP adapter (e.g. `GcpNlpClient`).
- Migrations: `alembic/` + `alembic/versions/`

Quick run & dev commands
```powershell
pip install -r requirements.txt
# add .env with LOCAL_DATABASE_URL and MEDIASTACK_API_KEY
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
python -m app.jobs.run_ingestion
pytest
```

Key rules Copilot MUST follow (university assessment requirements)
- Data minimisation: never persist full article bodies or raw HTML permanently. If storing extracted text, truncate to a safe max (e.g. 512–1024 chars) and set an `expires_at` TTL on that row.
- robots.txt & politeness: always fetch/cache `https://<domain>/robots.txt`, respect disallow rules for our UA, and set `crawl_jobs.status = 'FORBIDDEN_BY_ROBOTS'` when disallowed. Use per-domain rate limiting (2–3 concurrent, 1–2s delay) and exponential backoff for 429/503.
- User-Agent: use an honest UA string, e.g. `aifeelnews-bot (contact: your-email@example.com)`; do not impersonate browsers.
- Security: never hardcode secrets; use env vars or Secret Manager. Avoid logging long text or sensitive fields. Use parameterized DB queries (SQLAlchemy ORM preferred).

Database design highlights (follow these when adding models / migrations)
- `sources` (id, name, domain, country, category, created_at)
- `articles` (id, source_id, url UNIQUE, title, published_at, language, external_id, first_seen_at, last_seen_at)
- `crawl_jobs` (id, article_id, status ENUM, robots_allowed, http_status, fetched_at, bytes_downloaded, error_code, error_message, created_at, updated_at) — index on `status` and `article_id`
- `article_contents` (OPTIONAL short-lived snippets): content_text (TRUNCATED), content_hash, content_length, extracted_at, expires_at — ensure TTL cleanup job
- `sentiment_analyses` (article_id, provider, model_name, score, magnitude, label, language, analyzed_at) — allow multiple providers

Sentiment & GCP NL mapping
- Wrap GCP NL in an adapter `GcpNlpClient` and inject it where needed.
- Mapping guideline: score > 0.25 → positive, < -0.25 → negative, else neutral. Store provider=`GCP_NL` and model_name.
- Do not store full GCP JSON responses in Postgres; keep minimal fields only.

BigQuery
- Use a small `BigQuerySentimentRepository` class and the official Google client library to append rows to `article_sentiment_events` (partition by ingested_at). Do not call REST directly unless necessary.

APIs & business rules
- Public endpoints must not return full article bodies. Return metadata, sentiment indicators, and links to original URLs.
- Use dependency injection for DB sessions, GCP client, and BigQuery client.

Testing & CI hints
- Unit tests: content extraction, sentiment mapping, robots.txt logic, TTL cleanup.
- Integration tests: migrations + end-to-end ingestion with mocked Mediastack and mocked GCP NL client.

If you want, I can add a sample `.env` snippet, example Alembic migration template, or a minimal `GcpNlpClient` adapter + unit tests next. Reply which piece to generate.
