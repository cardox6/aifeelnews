"""Mock data for local development when Mediastack API is unavailable."""

from typing import Dict, List

# Sample mock articles matching Mediastack API response format
MOCK_ARTICLES = [
    {
        "title": "AI Revolution Transforms Healthcare Industry",
        "description": (
            "Revolutionary AI breakthrough promises to transform how we "
            "interact with technology in our daily lives."
        ),
        "url": "https://example.com/ai-healthcare-2025",
        "image": "https://picsum.photos/id/1/400/300",
        "published_at": "2025-11-18T10:30:00Z",
        "source": "TechNews",
        "language": "en",
        "country": "us",
        "category": "technology",
    },
    {
        "title": "Global Climate Summit Reaches Historic Agreement",
        "description": (
            "World leaders commit to ambitious carbon reduction targets "
            "in unprecedented international cooperation effort."
        ),
        "url": "https://example.com/climate-summit-2025",
        "image": "https://picsum.photos/id/2/400/300",
        "published_at": "2025-11-18T09:15:00Z",
        "source": "GlobalNews",
        "language": "en",
        "country": "gb",
        "category": "general",
    },
    {
        "title": "Breakthrough in Quantum Computing Announced",
        "description": (
            "Scientists achieve new milestone in quantum error correction, "
            "bringing practical quantum computers closer to reality."
        ),
        "url": "https://example.com/quantum-breakthrough-2025",
        "image": "https://picsum.photos/id/3/400/300",
        "published_at": "2025-11-18T08:45:00Z",
        "source": "ScienceDaily",
        "language": "en",
        "country": "us",
        "category": "science",
    },
    {
        "title": "Economic Markets Show Resilience Amid Uncertainty",
        "description": (
            "Financial analysts report steady growth indicators despite "
            "global economic challenges and geopolitical tensions."
        ),
        "url": "https://example.com/markets-resilience-2025",
        "image": "https://picsum.photos/id/4/400/300",
        "published_at": "2025-11-18T07:20:00Z",
        "source": "BusinessReport",
        "language": "en",
        "country": "us",
        "category": "business",
    },
]


def get_mock_articles_for_source(source_name: str) -> List[Dict]:
    """Return mock articles with the specified source name."""
    mock_articles = []
    for i, article in enumerate(MOCK_ARTICLES):
        mock_article = article.copy()
        mock_article["source_name"] = source_name
        # Modify URL to include source for uniqueness
        mock_article["url"] = f"{article['url']}-{source_name}-{i}"
        mock_articles.append(mock_article)

    return mock_articles


def fetch_mock_articles_from_source(source: str) -> List[Dict]:
    """Mock version of fetch_articles_from_source for local development."""
    print(f"→ Using MOCK data for {source} (Mediastack API unavailable)")
    return get_mock_articles_for_source(source)
