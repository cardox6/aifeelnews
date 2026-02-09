# aiFeelNews 📰💭

> **AI-powered news sentiment analysis platform for university project with research purposes**

A FastAPI-based news aggregation and sentiment analysis platform that ingests articles from Mediastack API, processes them with sentiment analysis, and provides a RESTful API for accessing news with emotional context.

## 🎯 Project Overview

**Core Features:**
- 📰 **News Ingestion**: Automated Mediastack API integration with English-only filtering
- 🕷️ **Ethical Web Crawling**: Full robots.txt compliance with respectful rate limiting
- 🧠 **Advanced Sentiment Analysis**: Multi-provider architecture (VADER + Google Cloud NL)
- 🗄️ **Privacy-First Database**: PostgreSQL with TTL-based content expiry and data minimization
- 🚀 **Production API**: FastAPI with OpenAPI documentation and health endpoints
- ⏰ **Automated Content Lifecycle**: TTL-based cleanup preventing long-term content storage
- 🛡️ **Security & Compliance**: Honest User-Agent, domain-based rate limiting, error handling
- 📅 **CI/CD Pipeline**: GitHub Actions with automated testing, building, and Cloud Run deployment
- 🎛️ **Configuration Management**: Environment-based settings with provider switching capabilities

## 🏗️ System Architecture

### Cloud Infrastructure
![Cloud Architecture Diagram](docs/Cloud_Architecture_Diagram.drawio.png)
*Figure 1 — Cloud architecture: GCP services, Firebase, CI/CD pipelines, and external integrations.*

### Application Data Flow
![Application Architecture Diagram](docs/Architechture_diagram-aifeelnews.drawio.png)
*Figure 2 — Application-level data flow: ingestion, sentiment analysis, storage, and API serving.*


## 🚀 Quick Start

### Security Notice
**Never commit your Firebase or Google Cloud service account JSON files to the repository.**
Service account credentials must be managed securely using Google Secret Manager. See below for setup instructions.


### ⚠️ Service Account Security

**Never commit your Firebase service account JSON to the repository.**
Instead, upload it to Google Secret Manager and mount it as an environment variable in Cloud Run. See below for details.




### Prerequisites
- Python 3.11+
- PostgreSQL (or use Docker Compose)
- Mediastack API key
- Firebase project (for authentication)
- Google Cloud project (for deployment, Secret Manager, Cloud Run)

### Environment Variables
Copy `.env.example` to `.env` and fill in the required values for both backend and frontend. Never commit secrets.

### Service Account Setup
1. In Firebase Console, generate a new service account key (JSON).
2. Upload it to Google Secret Manager:
   ```bash
   gcloud secrets create firebase-service-account-json \
     --data-file="firebase-service-account.json" \
     --replication-policy="automatic"
   ```
3. Grant access to your Cloud Run service account:
   ```bash
   gcloud secrets add-iam-policy-binding firebase-service-account-json \
     --member="serviceAccount:YOUR_CLOUD_RUN_SERVICE_ACCOUNT" \
     --role="roles/secretmanager.secretAccessor"
   ```
4. Update Cloud Run to mount the secret as an env var:
   ```bash
   gcloud run services update aifeelnews-web \
     --region=YOUR_REGION \
     --update-secrets=FIREBASE_SERVICE_ACCOUNT_JSON=firebase-service-account-json:latest
   ```

### Documentation
- See `docs/PROJECT_STRUCTURE.md` for a detailed overview of the backend and project layout.
- See `frontend/README.md` for frontend setup and deployment.

- Firebase project (for authentication)
- Firebase service account JSON (for backend auth, managed via Secret Manager)

### Environment Variables

See `.env.example` in both root and `frontend/` for required variables. Never commit secrets.

#### Backend (Cloud Run)
- `FIREBASE_SERVICE_ACCOUNT_JSON` should be set via Secret Manager, not as a file.

#### Frontend
- Uses Vite env vars (see `frontend/.env.example`). No service account JSON needed in frontend.

### Service Account Setup (Backend Auth)
1. Download your Firebase service account JSON from the Firebase Console.
2. Upload it to Google Secret Manager:
   ```bash
   gcloud secrets create firebase-service-account-json \
     --data-file="firebase-service-account.json" \
     --replication-policy="automatic"
   gcloud secrets add-iam-policy-binding firebase-service-account-json \
     --member="serviceAccount:YOUR_CLOUD_RUN_SERVICE_ACCOUNT" \
     --role="roles/secretmanager.secretAccessor"
   gcloud run services update aifeelnews-web \
     --region=YOUR_REGION \
     --update-secrets=FIREBASE_SERVICE_ACCOUNT_JSON=firebase-service-account-json:latest
   ```
3. Delete the JSON file from your repo and local folders after uploading.


## 🎯 CI/CD Pipeline

**GitHub Actions Automated Deployment** - Full CI/CD pipeline with Google Cloud Platform:

### Pipeline Features
- **✅ Automated Testing**: Runs flake8, mypy, and pytest on every commit
- **🐳 Container Build**: Builds and pushes Docker images to Google Container Registry
- **☁️ Cloud Deployment**: Deploys to Google Cloud Run with zero-downtime updates
- **🔐 Secure Authentication**: Service account-based authentication with proper IAM roles
- **📊 Quality Gates**: Code must pass all quality checks before deployment

### Pipeline Stages
1. **Test Stage**: Code quality checks (flake8, mypy, pytest with SQLite in-memory database)
2. **Build Stage**: Docker image build and push to `gcr.io/aifeelnews-prod/aifeelnews-web`
3. **Deploy Stage**: Cloud Run service deployment with environment variable injection

### Automated Deployment
Every push to `main` branch triggers:
```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloud Run
on:
  push:
    branches: [ main ]

jobs:
  test:
    - Code quality checks (flake8, mypy)
    - Unit tests with SQLite test database

  build-and-deploy:
    - Docker build and push to GCR
    - Cloud Run deployment
    - Health check verification
```

**Production URL**: https://aifeelnews-web-813770885946.europe-west1.run.app

### CI/CD Service Account Setup
```bash
# Service account with required roles
gcloud iam service-accounts create github-actions-sa --display-name="GitHub Actions"

# Grant necessary permissions
gcloud projects add-iam-policy-binding aifeelnews-prod \
  --member="serviceAccount:github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding aifeelnews-prod \
  --member="serviceAccount:github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding aifeelnews-prod \
  --member="serviceAccount:github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# Generate and store key as GitHub secret
gcloud iam service-accounts keys create github-actions-key.json \
  --iam-account=github-actions-sa@aifeelnews-prod.iam.gserviceaccount.com
```

**GitHub Secrets Required**:
- `GCP_SA_KEY`: Service account JSON key for authentication
- `GCP_PROJECT_ID`: Google Cloud project ID (`aifeelnews-prod`)

### Manual Deployment (if needed)
```bash
# Build and deploy manually
docker build -f docker/Dockerfile.web -t gcr.io/aifeelnews-prod/aifeelnews-web:latest .
docker push gcr.io/aifeelnews-prod/aifeelnews-web:latest

gcloud run deploy aifeelnews-web \
  --image gcr.io/aifeelnews-prod/aifeelnews-web:latest \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars ENV=production
```

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
| `/health` | GET | Service health check with database connectivity |
| `/ready` | GET | Kubernetes readiness check |
| `/articles` | GET | List articles with sentiment data |
| `/articles/{id}` | GET | Get specific article details |
| `/sources` | GET | List configured news sources |
| `/users` | GET/POST | User management |
| `/bookmarks` | GET/POST | User bookmarks |
| `/api/v1/sentiment/info` | GET | **NEW**: Current sentiment provider information |
| `/api/v1/trigger-ingestion` | POST | **Cloud Scheduler**: Trigger news ingestion pipeline |
| `/api/v1/cleanup` | POST | **Cloud Scheduler**: Database maintenance and TTL cleanup |

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
│   ├── config/                # Organized configuration classes
│   │   ├── __init__.py        # Main config object & legacy compatibility
│   │   ├── database.py        # Database connection settings
│   │   ├── ingestion.py       # Mediastack API & ingestion config
│   │   ├── crawler.py         # Web crawling settings
│   │   ├── scheduler.py       # Cloud Scheduler jobs & API optimization
│   │   └── ui.py              # UI/frontend configuration
│   ├── jobs/                  # Background processing
│   │   ├── run_ingestion.py   # Main ingestion pipeline
│   │   ├── run_crawl_worker.py # Crawl worker entry point
│   │   └── ...
│   ├── models/                # SQLAlchemy models
│   ├── routers/               # FastAPI endpoints
│   ├── schemas/               # Pydantic schemas
│   └── utils/                 # Utilities (sentiment, cleanup, secrets, robots.txt)
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

# Clean up expired content and maintain database health
curl -X POST http://localhost:8000/api/v1/cleanup

# Run crawl worker (local)
python app/jobs/run_crawl_worker.py

# Monitor multi-container services
docker-compose logs -f web worker scheduler

# Service health checks
curl http://localhost:8080/health     # Web API health
curl http://localhost:8080/ready      # Kubernetes readiness
```

## 🔧 Configuration

### Organized Configuration Structure

Configuration is organized into separate classes for better maintainability:

```python
# New organized approach (recommended)
from app.config import config

batch_size = config.ingestion.mediastack_fetch_limit
delay = config.crawler.crawler_default_delay
db_url = config.database.sqlalchemy_database_url

# Legacy approach (still works for backward compatibility)
from app.config import settings
batch_size = settings.MEDIASTACK_FETCH_LIMIT
```

**Configuration Classes:**
- `DatabaseConfig` - Database connections and environment settings
- `IngestionConfig` - Mediastack API and article ingestion settings
- `CrawlerConfig` - Web crawling and politeness configuration
- `SchedulerConfig` - Cloud Scheduler jobs and API usage optimization
- `UIConfig` - Frontend and display settings

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

*Note: Environment variable names remain exactly the same. The new configuration structure provides better organization while maintaining full backward compatibility.*

### 🔐 Security & Secret Management

**Production environments use Google Secret Manager for secure credential storage:**

- **API Keys**: `MEDIASTACK_API_KEY` → `mediastack-api-key` secret
- **Database Passwords**: `POSTGRES_PASSWORD` → `db-password` secret
- **Automatic Fallback**: Development environments use `.env` variables
- **Zero Code Changes**: Seamless transition between local and production

```python
# Configuration automatically handles both sources
from app.config import config
api_key = config.ingestion.mediastack_api_key  # Secret Manager or .env
```

**Security Features:**
- 🔒 **Encrypted Storage**: Secrets encrypted at rest in Google Secret Manager
- 🔄 **Environment Fallback**: Graceful fallback to environment variables
- 🚫 **No Hardcoded Values**: All sensitive data externalized
- 🔧 **Runtime Retrieval**: Secrets fetched securely at application startup

### Key Settings
- **Data Minimization**: Article bodies are never permanently stored (max 1024 chars)
- **TTL Cleanup**: Automatic cleanup of expired content snippets (7-day expiry)
- **Database Maintenance**: Automated cleanup of old crawl jobs and maintenance statistics
- **Rate Limiting**: Respectful crawling with domain-based delays and backoff
- **Robots.txt Compliance**: Full respect for website crawling policies
- **Ethical Crawling**: Honest User-Agent identification and request throttling

## 🧠 Advanced Sentiment Analysis

### Multi-Provider Architecture
**Flexible Provider Selection**: Environment-configurable sentiment analysis with seamless switching:

**🆓 VADER (Default)**:
- Fast, offline lexicon-based analysis
- Perfect for development and testing
- Zero API costs and dependencies
- Optimized for social media and news text

**☁️ Google Cloud Natural Language (Production)** ✅ **ACTIVE**:
- Enterprise-grade ML sentiment analysis
- Production-quality accuracy and insights
- Magnitude scoring for emotional intensity
- Support for 12+ languages
- Automatic fallback to VADER on errors
- **Currently deployed in production**

### Configuration
```bash
# Environment variable switching
SENTIMENT_PROVIDER=VADER          # Free, fast (default)
SENTIMENT_PROVIDER=GCP_NL         # Production ML analysis ✅ ACTIVE

# Google Cloud setup (configured in production)
GCP_PROJECT_ID=aifeelnews-prod
GCP_NLP_KEY_JSON=[stored in Secret Manager]
```

### Production Sentiment API
```bash
# Check current provider status
curl https://aifeelnews-web-813770885946.europe-west1.run.app/api/v1/sentiment/info

# Expected response:
{
  "provider": "GCP_NL",
  "fallback_enabled": true,
  "supported_languages": ["en","es","fr","de","it","pt","ru","ja","ko","zh","ar","hi"],
  "positive_threshold": 0.25,
  "negative_threshold": -0.25
}
```

### Optimization Features
- **English-Only Processing**: Optimized for our English news pipeline (no language detection overhead)
- **Graceful Fallbacks**: Automatic VADER fallback when GCP NL is unavailable
- **Error Handling**: Robust error handling prevents sentiment analysis failures from breaking ingestion
- **Provider Abstraction**: Consistent API regardless of underlying provider

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
- **Secret Management**: Google Secret Manager for production credential security
- **Environment Configuration**: 12-factor app methodology with secure secret handling
- **Stateless Services**: Database-driven job queuing for horizontal scaling

**Privacy & Ethics**: Full article bodies are never stored to respect copyright and minimize data footprint. Only metadata and brief excerpts with automatic expiration.

### ⏰ Cloud Scheduler Optimization

**Automated News Ingestion** with API usage optimization:

- **Schedule**: Every 8 hours (3 times daily: 00:00, 08:00, 16:00 UTC)
- **API Usage**: 45.7% of 10,000 monthly request limit
- **Daily Output**: ~3,750 articles with optimal freshness
- **Safety Buffer**: 54.3% remaining for traffic spikes and development

**Automated Database Cleanup**:

- **Schedule**: Daily at 2:00 AM UTC
- **TTL Cleanup**: Removes expired article content (respects privacy requirements)
- **Maintenance**: Cleans up old crawl jobs (7+ days old completed/failed records)
- **Statistics**: Provides comprehensive database health metrics

**Key Features:**
- **🎯 API Efficiency**: 50 requests per run × 3 daily = 4,566 monthly requests
- **🔄 Automatic Scaling**: Cloud Run handles traffic bursts seamlessly
- **🧹 Database Health**: Automated cleanup prevents database bloat
- **📊 Usage Monitoring**: Built-in estimation and tracking
- **⚙️ Configuration**: Easily adjustable via `SchedulerConfig`

**Setup Commands:**
```bash
# Deploy updated container with scheduler integration
docker build -f docker/Dockerfile.web -t gcr.io/project/aifeelnews-web .
docker push gcr.io/project/aifeelnews-web
gcloud run deploy aifeelnews-web --image gcr.io/project/aifeelnews-web

# Create Cloud Scheduler jobs (after deployment)
python scripts/create-scheduler-commands.py
# Or use the interactive setup script:
# python scripts/setup-cloud-scheduler.py

# Verify jobs are created
gcloud scheduler jobs list --location=europe-west1

# Test jobs manually
gcloud scheduler jobs run aifeelnews-ingestion --location=europe-west1
gcloud scheduler jobs run aifeelnews-cleanup --location=europe-west1
```

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

# Database cleanup and maintenance (automated via Cloud Scheduler)
curl -X POST http://localhost:8000/api/v1/cleanup

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
