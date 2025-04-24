from sqlalchemy.orm import Session
from database import SessionLocal
from models.article import Article

def clean_articles():
    db: Session = SessionLocal()

    print("⛔ Removing articles with missing titles or URLs...")
    removed_empty = db.query(Article).filter(
        (Article.title == None) | (Article.url == None)
    ).delete(synchronize_session=False)

    print(f"→ Removed {removed_empty} invalid entries.")

    print("⛔ Removing duplicates based on (title + source)...")
    seen = set()
    duplicates = []

    for article in db.query(Article).order_by(Article.published_at.desc()).all():
        key = (article.title.strip().lower(), article.source.lower() if article.source else "")
        if key in seen:
            duplicates.append(article.id)
        else:
            seen.add(key)

    if duplicates:
        deleted_count = db.query(Article).filter(Article.id.in_(duplicates)).delete(synchronize_session=False)
        print(f"→ Removed {deleted_count} duplicate entries.")
    else:
        print("→ No duplicates found.")

    db.commit()
    db.close()
    print("✅ Cleaning complete.")

if __name__ == "__main__":
    clean_articles()

# PYTHONPATH=. python jobs/clean_articles.py
