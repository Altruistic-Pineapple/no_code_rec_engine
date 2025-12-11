from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import UserActivityCreate, UserActivityRead, BatchActivityCreate

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
        rating=payload.rating,
        duration=payload.duration,
        session_id=payload.session_id,
        sequence_order=payload.sequence_order,
        metadata=payload.metadata
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

@router.post("/batch")
def log_batch_activity(payload: BatchActivityCreate, db: Session = Depends(get_db)):
    """
    Log multiple activities at once for efficiency.
    Useful for offline sync or bulk data collection.
    """
    activities = []
    for activity_data in payload.activities:
        activity = models.UserActivity(
            user_id=activity_data.user_id,
            mix_id=activity_data.mix_id,
            content_id=activity_data.content_id,
            event_type=activity_data.event_type,
            rating=activity_data.rating,
            duration=activity_data.duration,
            session_id=activity_data.session_id,
            sequence_order=activity_data.sequence_order,
            metadata=activity_data.metadata
        )
        activities.append(activity)
    
    db.add_all(activities)
    db.commit()
    
    return {
        "message": f"Logged {len(activities)} activities",
        "count": len(activities)
    }
