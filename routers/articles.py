from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.article import Article as ArticleModel
from schemas.article import ArticleRead

router = APIRouter(prefix="/articles", tags=["articles"])

@router.get("/", response_model=List[ArticleRead])
def get_articles(db: Session = Depends(get_db), limit: int = 20):
    return db.query(ArticleModel).order_by(ArticleModel.published_at.desc()).limit(limit).all()

@router.get("/{article_id}", response_model=ArticleRead)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(ArticleModel).filter_by(id=article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
