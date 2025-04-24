from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.article import Article as ArticleModel
from schemas.article import Article

router = APIRouter()

@router.get("/", response_model=List[Article])
def get_articles(db: Session = Depends(get_db), limit: int = 20):
    return db.query(ArticleModel).order_by(ArticleModel.published_at.desc()).limit(limit).all()
