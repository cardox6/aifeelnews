# aiFeelNews - Project Structure

This document outlines the organization of the aiFeelNews project for maintainability and clarity.

## 📁 Root Directory Structure

```
aifeelnews/
├── .github/                    # GitHub workflows and templates
├── .venv/                      # Python virtual environment
├── alembic/                    # Database migrations
├── app/                        # Main application code
├── docs/                       # Project documentation
├── scripts/                    # Utility and maintenance scripts
├── tests/                      # Test suite
├── .env.example               # Environment variables template
├── .flake8                    # Flake8 linting configuration
├── .gitignore                 # Git ignore patterns
├── .pre-commit-config.yaml    # Pre-commit hooks configuration
├── alembic.ini               # Alembic migration configuration
├── docker-compose.yml        # Docker services configuration
├── Dockerfile                # Application container definition
├── Makefile                  # Build and maintenance commands
├── pyproject.toml           # Python project metadata and tool config
├── pytest.ini              # Pytest configuration
└── requirements.txt         # Python dependencies
```

## 📱 Application Structure (`app/`)

```
app/
├── __init__.py              # Package initialization
├── main.py                  # FastAPI application entry point
├── config.py               # Application configuration (Pydantic settings)
├── database.py             # Database connection and session management
├── crud/                   # Database CRUD operations
├── jobs/                   # Background jobs and data processing
│   ├── fetch_from_mediastack.py  # API data fetching
│   ├── ingest_articles.py        # Article processing pipeline
│   ├── normalize_articles.py     # Data normalization
│   ├── run_ingestion.py          # Main ingestion orchestrator
│   ├── ttl_cleanup.py           # Database maintenance
│   └── sources_list.py          # Source management
├── models/                 # SQLAlchemy database models
│   ├── article.py         # Article model
│   ├── article_content.py # Article content with TTL
│   ├── bookmark.py        # User bookmarks
│   ├── crawl_job.py      # Web crawling jobs
│   ├── sentiment_analysis.py  # Sentiment analysis results
│   ├── source.py         # News sources
│   └── user.py           # User accounts
├── routers/              # FastAPI route handlers
│   ├── articles.py       # Article endpoints
│   ├── bookmarks.py      # Bookmark endpoints
│   ├── sources.py        # Source endpoints
│   └── users.py          # User endpoints
├── schemas/              # Pydantic data validation schemas
│   ├── article.py        # Article request/response schemas
│   ├── bookmark.py       # Bookmark schemas
│   ├── source.py         # Source schemas
│   └── user.py           # User schemas
└── utils/                # Utility functions
    └── sentiment.py      # Sentiment analysis utilities
```

## 🧪 Testing Structure (`tests/`)

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration and fixtures
├── test_ingestion.py        # Data ingestion pipeline tests
└── test_new_models.py       # Database model tests
```

## 🔧 Scripts Structure (`scripts/`)

```
scripts/
├── dev/                     # Development and debugging utilities
│   ├── test_api.py         # Manual API testing script
│   └── check_articles.py   # Database inspection utility
└── discover_sources.py     # Mediastack source discovery tool
```

## 📚 Documentation Structure (`docs/`)

```
docs/
└── PROJECT_STRUCTURE.md    # This file - project organization guide
```

## 🏗️ Database Migrations (`alembic/`)

```
alembic/
├── versions/               # Migration files (timestamped)
├── env.py                 # Alembic environment configuration
├── README                 # Alembic usage instructions
└── script.py.mako        # Migration template
```

## 🐳 Containerization

- **Dockerfile**: Multi-stage Python container with dependency optimization
- **docker-compose.yml**: Full stack with PostgreSQL and application services
- **Makefile**: Common development commands and Docker shortcuts

## 🔍 Code Quality

- **Pre-commit hooks**: Automated formatting and linting
- **Black**: Code formatting (configured in pyproject.toml)
- **isort**: Import organization
- **flake8**: Style checking (.flake8 config)
- **mypy**: Type checking (configured in pyproject.toml)

## 📋 Configuration Files

| File | Purpose |
|------|---------|
| `.env.example` | Environment variables template |
| `pyproject.toml` | Python project metadata, Black, isort, mypy config |
| `pytest.ini` | Test configuration and paths |
| `.flake8` | Style checking rules |
| `.pre-commit-config.yaml` | Git hooks for code quality |
| `alembic.ini` | Database migration settings |

## 🚀 Quick Start Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env  # Edit with your values

# Database
alembic upgrade head

# Development
uvicorn app.main:app --reload

# Testing
pytest

# Code Quality
pre-commit run --all-files

# Data Ingestion
python -m app.jobs.run_ingestion

# Utilities
python scripts/dev/check_articles.py
python scripts/discover_sources.py
```

## 📝 Notes

- **Data Privacy**: No full article content stored, only metadata + truncated snippets with TTL
- **Sentiment Analysis**: VADER (dev) → Google Cloud NL (production)
- **API Design**: RESTful with OpenAPI documentation at `/docs`
