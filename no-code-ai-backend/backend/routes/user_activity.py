from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import UserActivityCreate, UserActivityRead

router = APIRouter(prefix="/user-activity", tags=["user-activity"])

@router.get("/by-user/{user_id}", response_model=list[UserActivityRead])
def list_by_user(user_id: str, db: Session = Depends(get_db)):
    return (db.query(models.UserActivity)
              .filter(models.UserActivity.user_id == user_id)
              .order_by(models.UserActivity.timestamp.desc())
              .all())

@router.get("/by-mix/{mix_id}", response_model=list[UserActivityRead])
def list_by_mix(mix_id: str, db: Session = Depends(get_db)):
    return (db.query(models.UserActivity)
              .filter(models.UserActivity.mix_id == mix_id)
              .order_by(models.UserActivity.timestamp.desc())
              .all())
              
@router.post("", response_model=UserActivityRead)
def log_user_activity(payload: UserActivityCreate, db: Session = Depends(get_db)):
    rec = models.UserActivity(
        user_id=payload.user_id,
        mix_id=payload.mix_id,
        content_id=payload.content_id,
        event_type=payload.event_type,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec