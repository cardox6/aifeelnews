from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import get_current_user
from app.models.bookmark import Bookmark as BookmarkModel
from app.models.user import User
from app.schemas.bookmark import BookmarkCreate, BookmarkRead

router = APIRouter(tags=["Bookmarks"])


@router.post("/", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
def create_bookmark(
    bm: BookmarkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookmarkRead:
    bookmark = BookmarkModel(user_id=current_user.id, article_id=bm.article_id)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


@router.get("/", response_model=List[BookmarkRead])
def list_bookmarks(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> List[BookmarkRead]:
    bookmarks = db.query(BookmarkModel).filter_by(user_id=current_user.id).all()
    return bookmarks  # type: ignore[return-value,no-any-return]


@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    bookmark_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    bm = (
        db.query(BookmarkModel)
        .filter_by(id=bookmark_id, user_id=current_user.id)
        .first()
    )
    if not bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.delete(bm)
    db.commit()
