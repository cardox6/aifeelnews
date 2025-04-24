import os
import requests
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database import SessionLocal
from models.article import Article
from utils.sentiment import analyze_sentiment

API_KEY = os.getenv("MEDIASTACK_API_KEY")
BASE_URL = "https://api.mediastack.com/v1/news"
PLACEHOLDER_IMAGE = "https://picsum.photos/640/360"


SOURCES = [
    "dw",            # Deutsche Welle (Germany, global topics)
    "bbc",           # UK, broad coverage
    "cnn",           # US/global mainstream
    "bloomberg",     # Business/tech heavy
    "politico",      # Strong on EU/US policy
    "independent",   # UK, liberal leaning
    "time",          # US/global magazine
    "nytimes",       # US
    "abc-news-au",   # Australian news in English
    "guardian",      # UK, global   
    "skynews",
    "foreignpolicy",
    "businesstoday",
    "financialpost",
    "iotbusinessnews",
    "yahoo",
    "cnbc",
    "google-news",
    "scidev",
    "scitechdaily",
    "phys",
    "scienceandtechnologyresearchnews",
    "popsci",
]


params_template = {
    "access_key": API_KEY,
    "languages": "en",
    "sort": "published_desc",
    "categories": "general,business,health,science,technology,-sports,-entertainment",
}

def fetch_and_store():
    db: Session = SessionLocal()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for source in SOURCES:
        print(f"\n--- Fetching from source: {source} ---")
        params = params_template.copy()
        params["sources"] = source
        params["date"] = today_str

        try:
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()
        except Exception as e:
            print(f"Error fetching from {source}: {e}")
            continue

        data = response.json().get("data", [])
        print(f"Fetched {len(data)} articles from {source}")

        for item in data:
            if not item.get("description"):
                continue

            if db.query(Article).filter_by(url=item["url"]).first():
                continue

            if db.query(Article).filter_by(title=item["title"], source=item["source"]).first():
                continue

            try:
                text = f"{item['title']} {item['description']}"
                label, score = analyze_sentiment(text)

                published_raw = item.get("published_at")
                published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))

                article = Article(
                    source=item.get("source"),
                    title=item.get("title"),
                    description=item.get("description"),
                    url=item.get("url"),
                    image_url=item.get("image") or PLACEHOLDER_IMAGE,
                    published_at=published,
                    sentiment_label=label,
                    sentiment_score=score
                )
                db.add(article)
                print(f"Inserted: {item['title']}")

            except Exception as e:
                print(f"Error inserting article: {item['title']}")
                print(e)

    db.commit()
    db.close()

if __name__ == "__main__":
    fetch_and_store()