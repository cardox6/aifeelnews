from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.source import Source


def get_or_create_source(db: Session, name: str) -> Source:
    src = db.query(Source).filter_by(name=name).first()
    if not src:
        src = Source(name=name)
        db.add(src)
        db.flush()  # assigns src.id
    return src  # type: ignore[no-any-return]


def article_exists(db: Session, url: str) -> bool:
    return db.query(Article).filter_by(url=url).first() is not None


def ingest_articles(db: Session, articles: List[Dict]) -> int:
    """
    Insert each normalized dict into the DB if its canonical URL isn't
    already there. Handle duplicates within the same batch.

    Returns number of new rows.
    """
    added = 0
    seen_urls = set()  # Track URLs in current batch

    for a in articles:
        url = a["url"]

        # Skip if already exists in DB or already processed in this batch
        if article_exists(db, url) or url in seen_urls:
            continue

        src = get_or_create_source(db, a["source_name"])
        db.add(
            Article(
                title=a["title"],
                description=a["description"],
                url=url,
                image_url=a["image_url"],
                published_at=a["published_at"],
                language=a["language"],
                country=a["country"],
                category=a["category"],
                sentiment_label=a["sentiment_label"],
                sentiment_score=a["sentiment_score"],
                source_id=src.id,
            )
        )
        seen_urls.add(url)
        added += 1

    db.commit()
    return added
