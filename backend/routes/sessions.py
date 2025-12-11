from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import SessionCreate, SessionUpdate, SessionRead
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("", response_model=SessionRead)
def start_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """
    Start a new watch session for sequence tracking.
    """
    # Check if session already exists
    existing = db.query(models.WatchSession).filter(
        models.WatchSession.session_id == payload.session_id
    ).first()
    
    if existing:
        return existing
    
    session = models.WatchSession(
        session_id=payload.session_id,
        user_id=payload.user_id,
        mix_id=payload.mix_id,
        device_type=payload.device_type,
        context_data=payload.context_data
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.patch("/{session_id}", response_model=SessionRead)
def update_session(session_id: str, payload: SessionUpdate, db: Session = Depends(get_db)):
    """
    Update session with end time and total items viewed.
    """
    session = db.query(models.WatchSession).filter(
        models.WatchSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if payload.end_time:
        session.end_time = payload.end_time
    if payload.total_items_viewed:
        session.total_items_viewed = payload.total_items_viewed
    if payload.context_data:
        session.context_data = payload.context_data
    
    db.commit()
    db.refresh(session)
    return session

@router.get("/{session_id}", response_model=SessionRead)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get session details."""
    session = db.query(models.WatchSession).filter(
        models.WatchSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session

@router.get("/{session_id}/activities")
def get_session_activities(session_id: str, db: Session = Depends(get_db)):
    """
    Get all activities in a session, ordered by sequence.
    Used for sequence model training.
    """
    activities = db.query(models.UserActivity).filter(
        models.UserActivity.session_id == session_id
    ).order_by(models.UserActivity.sequence_order).all()
    
    return {
        "session_id": session_id,
        "activities": [
            {
                "content_id": a.content_id,
                "event_type": a.event_type,
                "sequence_order": a.sequence_order,
                "timestamp": a.timestamp.isoformat(),
                "duration": a.duration,
                "rating": a.rating
            }
            for a in activities
        ]
    }

@router.get("/user/{user_id}/history")
def get_user_session_history(user_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Get user's session history for sequence pattern analysis.
    """
    sessions = db.query(models.WatchSession).filter(
        models.WatchSession.user_id == user_id
    ).order_by(models.WatchSession.start_time.desc()).limit(limit).all()
    
    result = []
    for session in sessions:
        activities = db.query(models.UserActivity).filter(
            models.UserActivity.session_id == session.session_id
        ).order_by(models.UserActivity.sequence_order).all()
        
        result.append({
            "session_id": session.session_id,
            "mix_id": session.mix_id,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "total_items_viewed": session.total_items_viewed,
            "sequence": [a.content_id for a in activities if a.content_id]
        })
    
    return {
        "user_id": user_id,
        "sessions": result
    }
