import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend import models
from backend.database import SessionLocal

router = APIRouter()

# Pydantic schema for incoming request
class MixCreateRequest(BaseModel):
    title: str
    user_id: str = None  # Owner of this mix (external user ID)

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create")
def create_mix(request: MixCreateRequest, db: Session = Depends(get_db)):
    mix_id = str(uuid.uuid4())
    new_mix = models.Mix(
        id=mix_id,
        user_id=request.user_id,
        title=request.title,
        status="draft"
    )
    db.add(new_mix)
    db.commit()
    db.refresh(new_mix)
    return {
        "mix_id": new_mix.id,
        "user_id": new_mix.user_id,
        "title": new_mix.title,
        "status": new_mix.status
    }

