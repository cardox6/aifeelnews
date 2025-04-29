from sqlalchemy.orm import Session
from models.article import Article
from models.source  import Source

def get_or_create_source(db: Session, name: str) -> Source:
    src = db.query(Source).filter_by(name=name).first()
    if not src:
        src = Source(name=name)
        db.add(src)
        db.commit()
        db.refresh(src)
    return src

def article_exists(db: Session, url: str) -> bool:
    return db.query(Article).filter_by(url=url).first() is not None

def ingest_articles(db: Session, articles: list[dict]) -> int:
    inserted = 0
    for data in articles:
        if not article_exists(db, data["url"]):
            src = get_or_create_source(db, data["source_name"])
            art = Article(
                title           = data["title"],
                description     = data["description"],
                url             = data["url"],
                image_url       = data["image_url"],
                published_at    = data["published_at"],
                language        = data["language"],
                country         = data["country"],
                category        = data["category"],
                sentiment_label = data["sentiment_label"],
                sentiment_score = data["sentiment_score"],
                source_id       = src.id,
            )
            db.add(art)
            inserted += 1
    db.commit()
    return inserted
