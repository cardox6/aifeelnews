"""Mock data for local development when Mediastack API is unavailable."""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

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
    # German mock articles (language="de") so the EN/DE toggle, the
    # ?language=de filter, and the German analytics can be exercised locally
    # without a Mediastack API key.
    {
        "title": "Bundesregierung beschließt neues Klimaschutzgesetz",
        "description": (
            "Das Kabinett hat ein ambitioniertes Maßnahmenpaket zur Senkung "
            "der CO2-Emissionen verabschiedet, das Industrie und Verkehr "
            "gleichermaßen in die Pflicht nimmt."
        ),
        "url": "https://example.com/de/klimaschutzgesetz-2025",
        "image": "https://picsum.photos/id/10/400/300",
        "published_at": "2025-11-18T11:00:00Z",
        "source": "Tagesschau",
        "language": "de",
        "country": "de",
        "category": "general",
    },
    {
        "title": "Deutsche Wirtschaft wächst trotz globaler Unsicherheit",
        "description": (
            "Führende Ökonomen melden ein überraschend robustes Wachstum, "
            "getragen von starkem Export und stabiler Binnennachfrage."
        ),
        "url": "https://example.com/de/wirtschaft-wachstum-2025",
        "image": "https://picsum.photos/id/11/400/300",
        "published_at": "2025-11-18T10:15:00Z",
        "source": "Handelsblatt",
        "language": "de",
        "country": "de",
        "category": "business",
    },
    {
        "title": "Durchbruch in der Quantenforschung an deutscher Universität",
        "description": (
            "Forscher präsentieren einen neuen Ansatz zur Fehlerkorrektur, "
            "der praktische Quantencomputer ein gutes Stück näher rücken lässt."
        ),
        "url": "https://example.com/de/quantenforschung-2025",
        "image": "https://picsum.photos/id/12/400/300",
        "published_at": "2025-11-18T09:30:00Z",
        "source": "Spiegel",
        "language": "de",
        "country": "de",
        "category": "science",
    },
]


def _matches_languages(article: Dict, languages: str | None) -> bool:
    """True if the article's language is in the requested comma-separated set.

    Mirrors the real Mediastack ``languages`` param so a ``languages="de"``
    request (e.g. from the German backfill) returns only German mocks locally.
    ``None`` means no filter (return everything).
    """
    if not languages:
        return True
    wanted = {lang.strip() for lang in languages.split(",") if lang.strip()}
    return article.get("language") in wanted


def get_mock_articles_for_source(
    source_name: str, languages: str | None = None
) -> List[Dict]:
    """Return mock articles with the specified source name.

    ``languages`` filters by the article's language code to emulate the real
    Mediastack ``languages`` query param.
    """
    mock_articles = []
    for i, article in enumerate(MOCK_ARTICLES):
        if not _matches_languages(article, languages):
            continue
        mock_article = article.copy()
        mock_article["source_name"] = source_name
        # Modify URL to include source for uniqueness
        mock_article["url"] = f"{article['url']}-{source_name}-{i}"
        mock_articles.append(mock_article)

    return mock_articles


def fetch_mock_articles_from_source(
    source: str, languages: str | None = None
) -> List[Dict]:
    """Mock version of fetch_articles_from_source for local development."""
    # Use the logger (not print) so this never crashes on a non-UTF-8 console
    # (Windows cp1252 can't encode the arrow glyph) and matches the rest of the
    # job logging.
    logger.info("Using MOCK data for %s (Mediastack API unavailable)", source)
    return get_mock_articles_for_source(source, languages)
