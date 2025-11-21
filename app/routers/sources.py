from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.source import Source as SourceModel
from app.schemas.source import SourceCreate, SourceRead

router = APIRouter(tags=["Sources"])


@router.post("/", response_model=SourceRead)
def create_source(source_in: SourceCreate, db: Session = Depends(get_db)) -> SourceRead:
    existing = db.query(SourceModel).filter_by(name=source_in.name).first()
    if existing:
        raise HTTPException(400, "Source already exists")
    src = SourceModel(name=source_in.name)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


@router.get("/", response_model=List[SourceRead])
def list_sources(db: Session = Depends(get_db)) -> List[SourceRead]:
    return db.query(SourceModel).all()  # type: ignore[return-value,no-any-return]
