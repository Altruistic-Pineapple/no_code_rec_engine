from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, UserActivity, MixContent
import uuid
import random

router = APIRouter()

@router.post("/simulate-watch-data")
async def simulate_watch_data(payload: dict, db: Session = Depends(get_db)):
    """
    Simulate user watch data for testing Level 2/3 (Hybrid) recommendations.
    Creates/retrieves a test user and marks 2-3 TOP content items as watched.
    This ensures Level 2 and 3 will show clear differences from Level 1.
    """
    mix_id = payload.get('mix_id')
    if not mix_id:
        raise HTTPException(status_code=400, detail="mix_id required")
    
    # Get or create test user
    test_user_id = "test-user-001"
    test_user = db.query(User).filter(User.id == test_user_id).one_or_none()
    if not test_user:
        test_user = User(id=test_user_id, name="Test User")
        db.add(test_user)
        db.commit()
    
    # Get all content items for this mix
    content_items = db.query(MixContent).filter(MixContent.mix_id == mix_id).all()
    if not content_items:
        raise HTTPException(status_code=400, detail="No content items found for this mix")
    
    # Mark 2-3 of the TOP items as watched (to ensure visible differences in Level 2/3)
    # Use first N items and randomly select from those to ensure they'd be in recommendations
    num_watched = min(random.randint(2, 3), len(content_items))
    # Take from the first 10 items (most likely to be in recommendations)
    top_items = content_items[:min(10, len(content_items))]
    watched_items = random.sample(top_items, num_watched)
    
    # Clear any existing watch data for this test user/mix combo
    db.query(UserActivity).filter(
        UserActivity.user_id == test_user_id,
        UserActivity.mix_id == mix_id
    ).delete()
    db.commit()
    
    # Create watch records
    for item in watched_items:
        activity = UserActivity(
            user_id=test_user_id,
            mix_id=mix_id,
            content_id=item.content_id,
            event_type="watched"
        )
        db.add(activity)
    
    db.commit()
    
    watched_content_ids = [item.content_id for item in watched_items]
    print(f"DEBUG simulate_watch_data: Marked {len(watched_items)} items as watched: {watched_content_ids}")
    return {
        "user_id": test_user_id,
        "mix_id": mix_id,
        "watched_content_ids": watched_content_ids,
        "message": f"Simulated watch data: marked {len(watched_items)} items as watched"
    }
