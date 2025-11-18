import csv
import os

import requests

API_KEY = os.getenv("MEDIASTACK_API_KEY")
BASE_URL = "https://api.mediastack.com/v1/sources"

SEARCH_TERMS = [
    "politics",
    "election",
    "government",
    "policy",
    "economy",
    "business",
    "markets",
    "finance",
    "technology",
    "tech",
    "ai",
    "startup",
    "world",
    "international",
    "global",
    "security",
    "society",
    "justice",
    "equality",
    "social",
    "immigration",
    "refugees",
    "environment",
    "climate",
    "sustainability",
    "nature",
    "history",
    "archaeology",
    "anthropology",
    "culture",
    "science",
    "research",
    "innovation",
    "discovery",
]

seen_codes = set()
sources = []


def fetch_sources_by_keyword(keyword):
    params = {"access_key": API_KEY, "search": keyword, "languages": "en"}
    response = requests.get(BASE_URL, params=params)
    if response.status_code == 200:
        for source in response.json().get("data", []):
            code = source["code"]
            if code not in seen_codes:
                seen_codes.add(code)
                sources.append(source)


def save_sources_to_csv():
    with open("available_sources.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Code", "Name", "Category", "Country", "Language", "URL"])
        for src in sources:
            writer.writerow(
                [
                    src.get("code"),
                    src.get("name"),
                    src.get("category"),
                    src.get("country"),
                    src.get("language"),
                    src.get("url"),
                ]
            )
    print(f"Saved {len(sources)} unique sources to available_sources.csv")


if __name__ == "__main__":
    for term in SEARCH_TERMS:
        print(f"Searching sources with keyword: {term}")
        fetch_sources_by_keyword(term)
    save_sources_to_csv()
