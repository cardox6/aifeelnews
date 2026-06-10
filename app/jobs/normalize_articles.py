import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from dateutil import parser

from app.utils.sentiment import provisional_sentiment

logger = logging.getLogger(__name__)

# Article column limits (app/models/article.py). Over-length values raise a
# DataError on Postgres (SQLite silently truncates), so the normalizer is the
# place to enforce them: short metadata fields are truncated, while the
# identity/dedup fields (title, url) are skipped if they blow the limit, since
# a 1000+ char URL or 255+ char title signals a malformed record and
# truncating the URL would break its UNIQUE/dedup contract.
_TITLE_MAX = 255
_URL_MAX = 1000
_LANGUAGE_MAX = 2
_COUNTRY_MAX = 2
_CATEGORY_MAX = 50
_IMAGE_URL_MAX = 1000


def _clamp(value: Optional[str], limit: int) -> Optional[str]:
    """Truncate a string to ``limit`` chars; pass None through."""
    if value is None:
        return None
    return value[:limit]


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

        # parse date — dateutil raises ValueError on bad strings and
        # OverflowError on absurd values. published_at is NOT NULL downstream,
        # so a row with a missing or unparseable date is dropped here rather
        # than poisoning the batch insert with an IntegrityError. ``.get``
        # avoids a KeyError when the key is entirely absent.
        raw_published = item.get("published_at")
        if not isinstance(raw_published, str):
            logger.warning("Skipping article %s: missing published_at", canon)
            continue
        try:
            published = parser.isoparse(raw_published)
        except (ValueError, OverflowError) as e:
            logger.warning(
                "Skipping article %s: unparseable published_at: %s", canon, e
            )
            continue

        # Drop records whose identity fields exceed the column limits rather
        # than truncate them (truncating a URL would break the dedup contract).
        if len(title) > _TITLE_MAX or len(canon) > _URL_MAX:
            logger.warning("Skipping article %s: title/url exceeds column limit", canon)
            continue

        # Provisional sentiment via free VADER (never the metered GCP NL API):
        # the crawl worker's annotateText overwrites these fields with the
        # authoritative result, so calling GCP NL here too would double the spend.
        language = _clamp(item.get("language"), _LANGUAGE_MAX)
        label, score = provisional_sentiment(
            f"{title} {desc}", language=language or "en"
        )

        out.append(
            {
                "source_name": item["source_name"],
                "title": title,
                "description": desc,
                "url": canon,
                "image_url": _clamp(
                    item.get("image") or item.get("image_url"), _IMAGE_URL_MAX
                ),
                "published_at": published,
                "language": language,
                "country": _clamp(item.get("country"), _COUNTRY_MAX),
                "category": _clamp(item.get("category"), _CATEGORY_MAX),
                "sentiment_label": label,
                "sentiment_score": score,
            }
        )
    return out
