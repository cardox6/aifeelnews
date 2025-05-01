from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.bookmark import BookmarkCreate, BookmarkRead
from app.models.bookmark import Bookmark as BookmarkModel

# Auth, pull in current_user dependency

router = APIRouter(tags=["Bookmarks"])


@router.post("/", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    bm: BookmarkCreate,
    db: Session = Depends(get_db),
    # TODO: Replace with current_user dependency when Auth is ready
):
    # Stub user_id=1 until Auth integration
    bookmark = BookmarkModel(user_id=1, article_id=bm.article_id)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.get("/", response_model=List[BookmarkRead])
def list_bookmarks(
    db: Session = Depends(get_db),
    # TODO: Replace with current_user dependency when Auth is ready
):
    return db.query(BookmarkModel).filter_by(user_id=1).all()


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
    # TODO: Replace with current_user dependency when Auth is ready
):
    bm = db.query(BookmarkModel).filter_by(id=bookmark_id, user_id=1).first()
    if not bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.delete(bm)
    db.commit()
