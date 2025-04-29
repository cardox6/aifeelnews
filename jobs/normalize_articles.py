from datetime import datetime
from urllib.parse import urlparse, urlunparse
from utils.sentiment import analyze_sentiment
from config import settings

def canonicalize_url(raw_url: str) -> str:
    parts = urlparse(raw_url)
    # drop query + fragment + params
    clean = parts._replace(query="", fragment="", params="")
    return urlunparse(clean)

def normalize_articles(raw: list[dict]) -> list[dict]:
    out = []
    for item in raw:
        title = (item.get("title") or "").strip()
        desc  = (item.get("description") or "").strip()
        raw_url = item.get("url")
        if not (title and desc and raw_url):
            continue

        url = canonicalize_url(raw_url)
        try:
            published = datetime.fromisoformat(
                item["published_at"].replace("Z", "+00:00")
            )
        except Exception:
            continue

        # sentiment on title + description
        label, score = analyze_sentiment(f"{title} {desc}")

        out.append({
            "title":           title,
            "description":     desc,
            "url":             url,
            "image_url":       item.get("image") or settings.PLACEHOLDER_IMAGE,
            "published_at":    published,
            "language":        item.get("language"),
            "country":         item.get("country"),
            "category":        item.get("category"),
            "sentiment_label": label,
            "sentiment_score": score,
            "source_name":     item.get("source"),
        })
    return out
