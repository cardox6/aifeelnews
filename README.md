# aiFeelNews 📰💭

> **AI-powered news sentiment analysis platform for university project with research purposes**

A FastAPI-based news aggregation and sentiment analysis platform that ingests articles from Mediastack API, processes them with sentiment analysis, and provides a RESTful API for accessing news with emotional context.

## 🎯 Project Overview

**Core Features:**
- 📰 News ingestion from Mediastack API
- 🕷️ Ethical web crawling with robots.txt compliance
- 🧠 Sentiment analysis (VADER → Google Cloud NL)
- 🗄️ PostgreSQL database with proper data minimization
- 🚀 FastAPI REST API with OpenAPI docs
- ⏰ TTL-based content cleanup for privacy compliance
- 🛡️ Cybersecurity-compliant crawling with rate limiting

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL (or use Docker Compose)
- Mediastack API key

### Local Development

```bash
# Clone and setup
git clone <repository-url>
cd aifeelnews

# Install dependencies
pip install -r requirements.txt

# Environment setup
cp .env.example .env
# Edit .env with your Mediastack API key and database URL

# Database setup
alembic upgrade head

# Run ingestion pipeline
python -m app.jobs.run_ingestion

# Run crawl worker separately
python app/jobs/run_crawl_worker.py

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Multi-Container Docker

```bash
# Start all services (web API, worker, scheduler, database)
docker-compose up -d

# Check service health
docker-compose ps
curl http://localhost:8080/health

# View logs for specific services
docker-compose logs web
docker-compose logs worker
docker-compose logs scheduler

# Run one-time ingestion
docker-compose exec scheduler python -m app.jobs.run_ingestion

# Stop all services
docker-compose down
```

### Production Docker

```bash
# Test production configuration locally
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up

# Build individual services
docker build -f docker/Dockerfile.web -t aifeelnews-web .
docker build -f docker/Dockerfile.worker -t aifeelnews-worker .
docker build -f docker/Dockerfile.scheduler -t aifeelnews-scheduler .
```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/docs` | GET | Interactive API documentation |
| `/articles` | GET | List articles with sentiment data |
| `/articles/{id}` | GET | Get specific article details |
| `/sources` | GET | List configured news sources |
| `/users` | GET/POST | User management |
| `/bookmarks` | GET/POST | User bookmarks |

**Example API Response:**
```json
{
  "id": 1,
  "title": "Breaking: AI Revolution in Healthcare",
  "description": "New developments in medical AI...",
  "url": "https://example.com/article",
  "published_at": "2024-11-18T15:30:00Z",
  "sentiment_label": "positive",
  "sentiment_score": 0.8472,
  "source": {
    "name": "TechNews",
    "domain": "technews.com"
  }
}
```

## 🗂️ Project Structure

**Multi-Container Architecture:** Separate services for scalability and deployment flexibility.

```
aifeelnews/
├── docker/                     # Container configurations
│   ├── Dockerfile.web          # FastAPI web service  
│   ├── Dockerfile.worker       # Background crawl worker
│   ├── Dockerfile.scheduler    # Scheduled ingestion jobs
│   └── README.md              # Docker documentation
├── app/                       # Application code
│   ├── jobs/                  # Background processing
│   │   ├── run_ingestion.py   # Main ingestion pipeline
│   │   ├── run_crawl_worker.py # Crawl worker entry point
│   │   └── ...
│   ├── models/                # SQLAlchemy models
│   ├── routers/               # FastAPI endpoints
│   ├── schemas/               # Pydantic schemas  
│   └── utils/                 # Utilities (sentiment, BigQuery)
├── tests/                     # Test suite
│   └── test_crawl_worker.py   # Worker tests
├── scripts/                   # Development utilities
├── docs/                      # Documentation
├── alembic/                   # Database migrations
├── docker-compose.yml         # Development multi-container
├── docker-compose.prod.yml    # Production configuration
└── .env                       # Environment variables (not committed)
```

### Service Architecture

- **🌐 Web Service** (`docker/Dockerfile.web`): FastAPI API server with health checks
- **🕷️ Worker Service** (`docker/Dockerfile.worker`): Background web crawling and content processing  
- **⏰ Scheduler Service** (`docker/Dockerfile.scheduler`): Periodic ingestion from Mediastack API
- **🗄️ Database Service**: PostgreSQL with automated migrations

## 🧪 Development

### Code Quality
```bash
# Install pre-commit hooks
pre-commit install

# Run all quality checks
pre-commit run --all-files

# Individual tools
black .                    # Code formatting
isort .                   # Import sorting
flake8 .                  # Style checking
mypy .                    # Type checking
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Test specific module
pytest tests/test_ingestion.py -v
```

### Development Utilities
```bash
# Check recent articles
python scripts/check_articles.py

# Discover available sources  
python scripts/discover_sources.py

# Clean up expired content
python -m app.jobs.ttl_cleanup

# Run crawl worker (local)
python app/jobs/run_crawl_worker.py

# Monitor multi-container services
docker-compose logs -f web worker scheduler

# Service health checks
curl http://localhost:8080/health     # Web API health
curl http://localhost:8080/ready      # Kubernetes readiness
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Database
LOCAL_DATABASE_URL=postgresql://user:pass@localhost:5432/aifeelnews_dev

# Mediastack API
MEDIASTACK_API_KEY=your_api_key_here
MEDIASTACK_BASE_URL=https://api.mediastack.com/v1/news
MEDIASTACK_FETCH_LIMIT=25

# Application
ENV=local
```

### Key Settings
- **Data Minimization**: Article bodies are never permanently stored (max 1024 chars)
- **TTL Cleanup**: Automatic cleanup of expired content snippets (7-day expiry)
- **Rate Limiting**: Respectful crawling with domain-based delays and backoff
- **Robots.txt Compliance**: Full respect for website crawling policies
- **Ethical Crawling**: Honest User-Agent identification and request throttling

## 🏗️ Multi-Service Architecture

### Container Services

**🌐 Web API Service** (`docker/Dockerfile.web`)
- FastAPI application with OpenAPI docs
- Health check endpoints (`/health`, `/ready`) 
- Database migrations on startup
- Optimized for GCP Cloud Run

**🕷️ Background Worker Service** (`docker/Dockerfile.worker`)  
- Processes crawl jobs from database queue
- Ethical web crawling with robots.txt compliance
- Content extraction and sentiment analysis
- Automatic retry with exponential backoff

**⏰ Scheduler Service** (`docker/Dockerfile.scheduler`)
- Periodic ingestion from Mediastack API
- Runs every hour in production
- Creates crawl jobs for worker processing
- Handles API rate limiting

### Data Flow
1. **📥 Scheduler**: Fetches metadata from Mediastack API → creates crawl jobs
2. **🕷️ Worker**: Processes crawl jobs → extracts content → runs sentiment analysis  
3. **💾 Storage**: Persists minimal metadata with TTL content snippets
4. **🌐 API**: Serves processed data via REST endpoints
5. **🧹 Cleanup**: Automatic TTL cleanup of expired content

### Database Design
- `sources` - News source configuration
- `articles` - Article metadata with sentiment scores
- `crawl_jobs` - Web crawling queue with robots.txt compliance status
- `article_contents` - Short-term content snippets (TTL-managed, max 1024 chars)
- `sentiment_analyses` - Multiple provider sentiment results (VADER → GCP NL)
- `users` & `bookmarks` - User functionality

### Ethical Crawling Framework
- **🤖 Robots.txt Compliance**: Full respect for website crawling policies
- **⏱️ Rate Limiting**: Domain-based delays with exponential backoff
- **🔍 Content Extraction**: BeautifulSoup-based text extraction (no full storage)
- **📊 Status Tracking**: Comprehensive crawl job monitoring and error handling
- **🔒 Data Minimization**: Content truncated to 1024 chars with 7-day TTL

### Cloud-Ready Design
- **Container Isolation**: Separate services for independent scaling
- **Health Monitoring**: Kubernetes-compatible health and readiness probes
- **Environment Configuration**: 12-factor app methodology with env vars
- **Stateless Services**: Database-driven job queuing for horizontal scaling

**Privacy & Ethics**: Full article bodies are never stored to respect copyright and minimize data footprint. Only metadata and brief excerpts with automatic expiration.

## 📈 Monitoring & Maintenance

### Multi-Container Monitoring
```bash
# Check all service health
docker-compose ps

# View real-time logs from all services
docker-compose logs -f

# Monitor specific services
docker-compose logs -f web worker scheduler

# Check service health endpoints
curl http://localhost:8080/health     # API health with DB connectivity
curl http://localhost:8080/ready      # Readiness probe

# View API documentation
curl http://localhost:8080/docs
```

### Database & Jobs
```bash
# Check recent articles and crawl status
python scripts/check_articles.py

# Run one-time ingestion
docker-compose exec scheduler python -m app.jobs.run_ingestion

# Clean up expired content 
python -m app.jobs.ttl_cleanup

# Check worker job processing
docker-compose exec worker python app/jobs/run_crawl_worker.py --dry-run
```

### Production Monitoring
- **Health Checks**: `/health` endpoint tests database connectivity
- **Readiness Probes**: `/ready` endpoint for Kubernetes deployment  
- **Service Logs**: Structured logging with correlation IDs
- **Job Monitoring**: Database-driven crawl job status tracking

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Install pre-commit hooks (`pre-commit install`)
4. Make changes with proper tests
5. Ensure all quality checks pass (`pre-commit run --all-files`)
6. Commit changes (`git commit -m 'Add amazing feature'`)
7. Push to branch (`git push origin feature/amazing-feature`)
8. Open Pull Request

## 📄 License

This project is for educational/research/assessment purposes.

## 🆘 Troubleshooting

### Common Issues

**Multi-Container Issues**
```bash
# Rebuild containers after code changes
docker-compose build

# Check service logs for errors
docker-compose logs web worker scheduler

# Restart specific services
docker-compose restart worker

# Clean restart all services
docker-compose down && docker-compose up -d
```

**Database Connection Error**
```bash
# Check PostgreSQL container is running
docker-compose ps db

# Test database connectivity
docker-compose exec db psql -U postgres -d aifeelnews -c "SELECT 1;"

# Check environment variables are loaded
docker-compose exec web env | grep DATABASE_URL
```

**Health Check Failures**
```bash
# Test health endpoints directly
curl -v http://localhost:8080/health
curl -v http://localhost:8080/ready

# Check web service logs  
docker-compose logs web

# Verify database migrations
docker-compose exec web alembic current
```

**Mediastack API Issues** 
```bash
# Verify API key in container
docker-compose exec scheduler env | grep MEDIASTACK

# Test API directly
curl "https://api.mediastack.com/v1/news?access_key=YOUR_KEY&limit=1"

# Run ingestion with debugging
docker-compose exec scheduler python -m app.jobs.run_ingestion
```

For more help, check the logs or open an issue!