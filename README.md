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

### Installation

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

# Run ingestion (includes crawling)
python -m app.jobs.run_ingestion

# Run crawl worker separately
python run_crawl_worker.py

# Start API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using Docker

```bash
# Full stack with PostgreSQL
docker-compose up --build

# Run ingestion in container
docker-compose run --rm web python -m app.jobs.run_ingestion

# Run crawl worker in container
docker-compose run --rm web python run_crawl_worker.py
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

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for detailed organization.

```
aifeelnews/
├── app/                    # FastAPI application
│   ├── jobs/              # Background processing
│   ├── models/            # Database models  
│   ├── routers/           # API endpoints
│   └── schemas/           # Request/response validation
├── tests/                 # Test suite
├── scripts/               # Utility scripts
│   └── dev/              # Development tools
├── docs/                  # Documentation
└── alembic/              # Database migrations
```

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
python scripts/dev/check_articles.py

# Test API endpoints
python scripts/dev/test_api.py

# Discover available sources
python scripts/discover_sources.py

# Clean up expired content
python -m app.jobs.ttl_cleanup

# Run crawl worker
python run_crawl_worker.py

# List available dev utilities
python -m scripts.dev
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

## 🏗️ Architecture

### Data Flow
1. **Ingestion**: Fetch metadata from Mediastack API
2. **Normalization**: Clean and structure article data
3. **Sentiment Analysis**: Apply VADER sentiment scoring
4. **Storage**: Persist minimal metadata (no full content)
5. **API**: Serve processed data via REST endpoints
6. **TTL Cleanup**: Remove expired content snippets

### Database Design
- `sources` - News source configuration
- `articles` - Article metadata with sentiment
- `crawl_jobs` - Web crawling status tracking with robots.txt compliance
- `article_contents` - Short-term content snippets (TTL, max 1024 chars)
- `sentiment_analyses` - Multiple provider sentiment results
- `users` & `bookmarks` - User functionality

### Crawling Architecture
- **Ethical Crawling**: robots.txt compliance and rate limiting
- **Content Extraction**: BeautifulSoup-based text extraction
- **Data Minimization**: Content truncated and TTL-managed
- **Status Tracking**: Comprehensive crawl job monitoring
- **Error Handling**: Graceful failure with detailed logging

**Privacy & Ethics**: Full article bodies are never stored to respect copyright and minimize data footprint. Only metadata and brief excerpts with automatic expiration.

## 📈 Monitoring & Maintenance

```bash
# Check database health
python scripts/dev/check_articles.py

# Monitor ingestion logs
python -m app.jobs.run_ingestion

# Clean up expired data
python -m app.jobs.ttl_cleanup

# View API metrics
curl http://localhost:8000/docs
```

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

**Database Connection Error**
```bash
# Check PostgreSQL is running
docker-compose up db

# Verify connection string in .env
LOCAL_DATABASE_URL=postgresql://...
```

**Import Errors**
```bash
# Ensure you're in project root and venv is active
cd aifeelnews
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

**Mediastack API Issues** 
```bash
# Check API key is set
echo $MEDIASTACK_API_KEY

# Test API directly
curl "https://api.mediastack.com/v1/news?access_key=YOUR_KEY&limit=1"
```

For more help, check the logs or open an issue!