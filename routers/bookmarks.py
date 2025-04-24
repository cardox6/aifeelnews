from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.bookmark import Bookmark as BookmarkModel
from models.article import Article as ArticleModel
from models.user import User as UserModel
from schemas.bookmark import BookmarkCreate, BookmarkOut
from fastapi import status

router = APIRouter()

@router.post("/", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
def add_bookmark(bookmark: BookmarkCreate, db: Session = Depends(get_db)):
    article = db.query(ArticleModel).filter(ArticleModel.id == bookmark.article_id).first()
    user = db.query(UserModel).filter(UserModel.id == bookmark.user_id).first()

    if not article or not user:
        raise HTTPException(status_code=404, detail="Article or user not found")

    existing = db.query(BookmarkModel).filter_by(user_id=user.id, article_id=article.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Bookmark already exists")

    new = BookmarkModel(user_id=user.id, article_id=article.id)
    db.add(new)
    db.commit()
    db.refresh(new)
    return new

@router.get("/user/{user_id}", response_model=List[BookmarkOut])
def get_user_bookmarks(user_id: int, db: Session = Depends(get_db)):
    return db.query(BookmarkModel).filter(BookmarkModel.user_id == user_id).all()
