# Get a single mix by ID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models

router = APIRouter()


class UpdateMixRequest(BaseModel):
    title: str = None


@router.get("/{mix_id}")
def get_mix(mix_id: str, db: Session = Depends(get_db)):
    """Get a single mix by ID."""
    mix = db.query(models.Mix).filter(models.Mix.id == mix_id).first()
    
    if not mix:
        raise HTTPException(status_code=404, detail="Mix not found")
    
    return {
        "mix_id": mix.id,
        "title": mix.title,
        "status": mix.status,
        "created_at": mix.created_at,
    }


@router.put("/{mix_id}/update")
def update_mix(mix_id: str, request: UpdateMixRequest, db: Session = Depends(get_db)):
    """Update a mix's title."""
    mix = db.query(models.Mix).filter(models.Mix.id == mix_id).first()
    
    if not mix:
        raise HTTPException(status_code=404, detail="Mix not found")
    
    # Update title if provided
    if request.title is not None:
        mix.title = request.title
    
    db.commit()
    db.refresh(mix)
    
    return {
        "mix_id": mix.id,
        "title": mix.title,
        "updated": True
    }
