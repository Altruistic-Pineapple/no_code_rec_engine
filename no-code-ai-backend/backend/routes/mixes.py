from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from backend.database import get_db
from backend import models
from backend.schemas import MixRead

router = APIRouter(prefix="/mixes", tags=["mixes"])

@router.get("", response_model=List[MixRead])
def list_mixes(
    db: Session = Depends(get_db),
    title: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    q: Optional[str] = None,            # keyword search in title
    limit: int = 50,
    offset: int = 0,
):
    qry = db.query(models.Mix)

    if title:
        qry = qry.filter(models.Mix.title == title)
    if status:
        qry = qry.filter(models.Mix.status == status)
    if date_from:
        qry = qry.filter(models.Mix.created_at >= date_from)
    if date_to:
        qry = qry.filter(models.Mix.created_at < date_to)
    if q:
        qry = qry.filter(models.Mix.title.ilike(f"%{q}%"))  # case-insensitive

    return (qry
            .order_by(models.Mix.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all())
