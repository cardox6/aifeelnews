import os
import requests
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models.article import Article
from utils.sentiment import analyze_sentiment

API_KEY = os.getenv("MEDIASTACK_API_KEY")
BASE_URL = "http://api.mediastack.com/v1/news"

def fetch_and_store():
    db: Session = SessionLocal()
    params = {
        "access_key": API_KEY,
        "languages": "en",
        "sort": "published_desc",
        "limit": 50,
    }

    response = requests.get(BASE_URL, params=params)

    print("Request URL:", response.url)
    print("Status:", response.status_code)
    
    data = response.json().get("data", [])
    print(f"Fetched {len(data)} articles")

    for item in data:
        if not item.get("description"):
            print(f"Skipping article with no description: {item['title']}")
            continue

        if db.query(Article).filter_by(url=item["url"]).first():
            print(f"Duplicate article (skipped): {item['title']}")
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
                image_url=item.get("image"),
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
