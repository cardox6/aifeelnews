import logging
from typing import Dict, List
from urllib.parse import urlparse, urlunparse

from dateutil import parser

from app.utils.sentiment import analyze_sentiment

logger = logging.getLogger(__name__)


def normalize_articles(raw: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for item in raw:
        title = item.get("title", "").strip()
        desc = item.get("description", "").strip()
        orig_url = item.get("url")
        if not title or not desc or not orig_url:
            continue

        # canonical URL: drop query & fragment
        p = urlparse(orig_url)
        canon = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))

        key = (canon, item["source_name"])
        if key in seen:
            continue
        seen.add(key)

        # parse date — dateutil raises ValueError on bad strings, TypeError
        # when passed something non-stringy (None, int) and OverflowError
        # on absurd values. Catch the data-shape failures, let anything
        # else propagate.
        try:
            published = parser.isoparse(item["published_at"])
        except (ValueError, TypeError, OverflowError) as e:
            logger.warning("Failed to parse published_at for article %s: %s", canon, e)
            published = None

        # sentiment
        label, score = analyze_sentiment(f"{title} {desc}")

        out.append(
            {
                "source_name": item["source_name"],
                "title": title,
                "description": desc,
                "url": canon,
                "image_url": item.get("image") or item.get("image_url"),
                "published_at": published,
                "language": item.get("language"),
                "country": item.get("country"),
                "category": item.get("category"),
                "sentiment_label": label,
                "sentiment_score": score,
            }
        )
    return out
