from database import SessionLocal
from models.article import Article

db = SessionLocal()
articles = db.query(Article).order_by(Article.published_at.desc()).limit(5).all()

for a in articles:
    print(f"{a.published_at} | {a.title} | {a.sentiment_label} ({a.sentiment_score})")
