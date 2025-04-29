import os
import requests
from typing import List, Dict

MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY")
SOURCES = [
    "dw", "bbc", "cnn", "bloomberg", "politico", "independent", "time", "nytimes",
    "abc-news-au", "guardian", "skynews", "foreignpolicy", "businesstoday",
    "financialpost", "iotbusinessnews", "yahoo", "cnbc", "google-news", "scidev",
    "scitechdaily", "phys", "scienceandtechnologyresearchnews", "popsci",
]
BASE_URL = "http://api.mediastack.com/v1/news"
CATEGORIES_FILTER = "-sports,-health, -entertainment"  # exclude sports and health

def fetch_articles_from_sources(source: str) -> List[Dict]:
    params = {
        "access_key": MEDIASTACK_API_KEY,
        "sources": source,
        "limit": 25,
        "categories": CATEGORIES_FILTER,
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])

def fetch_all_articles() -> List[Dict]:
    all_articles = []
    for source in SOURCES:
        try:
            articles = fetch_articles_from_sources(source)
            all_articles.extend(articles)
        except Exception as e:
            print(f"Error fetching articles from {source}: {e}")
    return all_articles