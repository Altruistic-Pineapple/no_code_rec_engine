# Get a single mix by ID with its quality level

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models

router = APIRouter()


class UpdateMixRequest(BaseModel):
    quality_level: int


@router.get("/{mix_id}")
def get_mix(mix_id: str, db: Session = Depends(get_db)):
    """Get a single mix by ID, including its quality level."""
    mix = db.query(models.Mix).filter(models.Mix.id == mix_id).first()
    
    if not mix:
        raise HTTPException(status_code=404, detail="Mix not found")
    
    return {
        "mix_id": mix.id,
        "title": mix.title,
        "status": mix.status,
        "quality_level": mix.quality_level,
        "created_at": mix.created_at,
    }


@router.put("/{mix_id}/update")
def update_mix(mix_id: str, request: UpdateMixRequest, db: Session = Depends(get_db)):
    """Update a mix's quality level."""
    mix = db.query(models.Mix).filter(models.Mix.id == mix_id).first()
    
    if not mix:
        raise HTTPException(status_code=404, detail="Mix not found")
    
    if request.quality_level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Quality level must be 1, 2, or 3")
    
    mix.quality_level = str(request.quality_level)
    db.commit()
    db.refresh(mix)
    
    return {
        "mix_id": mix.id,
        "title": mix.title,
        "quality_level": mix.quality_level,
        "updated": True
    }
