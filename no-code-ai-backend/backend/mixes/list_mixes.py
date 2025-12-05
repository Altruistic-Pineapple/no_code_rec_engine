# This route returns all saved mixes from the database

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models

# Create a router to group related routes
router = APIRouter()


# GET route to return a list of mixes with optional filters
@router.get("/")
def list_mixes(
    user_id: Optional[str] = None,
    title: Optional[str] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """List mixes with optional filters:

    - user_id: filter by owner (required for user-specific mixes)
    - title: case-insensitive substring match on mix title
    - q: space-separated keywords; all keywords must be present in title (AND)
    - status: exact match on mix status
    - created_after / created_before: ISO datetimes to filter by created_at
    """
    qry = db.query(models.Mix)
    
    # Filter by user_id if provided
    if user_id:
        qry = qry.filter(models.Mix.user_id == user_id)

    # title substring filter (legacy/single string)
    if title:
        qry = qry.filter(models.Mix.title.ilike(f"%{title}%"))

    # keyword search: split on whitespace and require each keyword to appear
    # in the title (case-insensitive)
    if q:
        keywords = [kw.strip() for kw in q.split() if kw.strip()]
        for kw in keywords:
            qry = qry.filter(models.Mix.title.ilike(f"%{kw}%"))

    if status:
        q = q.filter(models.Mix.status == status)

    if created_after:
        q = q.filter(models.Mix.created_at >= created_after)

    if created_before:
        q = q.filter(models.Mix.created_at <= created_before)

    mixes = qry.all()

    # Return a simplified list of mix info
    return [
        {
            "mix_id": mix.id,
            "title": mix.title,
            "status": mix.status,
            "created_at": mix.created_at,
        }
        for mix in mixes
    ]