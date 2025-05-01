from typing import List, Dict
from sqlalchemy.orm import Session
from app.models.source import Source
from app.models.article import Article


def get_or_create_source(db: Session, name: str) -> Source:
    src = db.query(Source).filter_by(name=name).first()
    if not src:
        src = Source(name=name)
        db.add(src)
        db.flush()  # assigns src.id
    return src


def article_exists(db: Session, url: str) -> bool:
    return db.query(Article).filter_by(url=url).first() is not None


def ingest_articles(db: Session, articles: List[Dict]) -> int:
    """
    Insert each normalized dict into the DB if its canonical URL isn't already there.
    Returns number of new rows.
    """
    added = 0
    for a in articles:
        if not article_exists(db, a["url"]):
            src = get_or_create_source(db, a["source_name"])
            db.add(
                Article(
                    title=a["title"],
                    description=a["description"],
                    url=a["url"],
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
            added += 1
    db.commit()
    return added
