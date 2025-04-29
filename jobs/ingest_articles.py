from typing import List, Dict
from sqlalchemy.orm import Session
from models.article import Article
from models.source import Source

def get_or_create_source(db: Session, source_name: str) -> Source:
    """Get or create a Source object by name."""
    source = db.query(Source).filter_by(name=source_name).first()
    if not source:
        source = Source(name=source_name)
        db.add(source)
        db.commit()
        db.refresh(source)
    return source

def article_exists(db: Session, url: str) -> bool:
    """Check if an article with the given URL already exists."""
    return db.query(Article).filter_by(url=url).first() is not None

def ingest_articles(db: Session, articles: List[Dict]):
    """Insert normalized articles into the database."""
    for article_data in articles:
        if article_data["url"] and not article_exists(db, article_data["url"]):
            source = get_or_create_source(db, article_data["source_name"])
            article = Article(
                title=article_data["title"],
                description=article_data["description"],
                url=article_data["url"],
                image_url=article_data["image_url"],
                published_at=article_data["published_at"],
                language=article_data["language"],
                country=article_data["country"],
                category=article_data["category"],
                source_id=source.id,
            )
            db.add(article)
    db.commit()
