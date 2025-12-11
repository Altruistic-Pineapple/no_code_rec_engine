from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models
from backend.schemas import RatingCreate, RatingRead

router = APIRouter(prefix="/ratings", tags=["ratings"])

@router.post("", response_model=RatingRead)
def create_or_update_rating(payload: RatingCreate, db: Session = Depends(get_db)):
    """
    Create or update a user's rating for a content item.
    Used for collaborative filtering.
    """
    # Check if rating already exists
    existing = db.query(models.UserItemRating).filter(
        models.UserItemRating.user_id == payload.user_id,
        models.UserItemRating.content_id == payload.content_id
    ).first()
    
    if existing:
        # Update existing rating
        existing.rating = payload.rating
        existing.rating_type = payload.rating_type
        existing.mix_id = payload.mix_id
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new rating
        rating = models.UserItemRating(
            user_id=payload.user_id,
            mix_id=payload.mix_id,
            content_id=payload.content_id,
            rating=payload.rating,
            rating_type=payload.rating_type
        )
        db.add(rating)
        db.commit()
        db.refresh(rating)
        return rating

@router.get("/user/{user_id}", response_model=list[RatingRead])
def get_user_ratings(user_id: str, db: Session = Depends(get_db)):
    """Get all ratings by a specific user."""
    return db.query(models.UserItemRating).filter(
        models.UserItemRating.user_id == user_id
    ).order_by(models.UserItemRating.updated_at.desc()).all()

@router.get("/content/{content_id}", response_model=list[RatingRead])
def get_content_ratings(content_id: str, db: Session = Depends(get_db)):
    """Get all ratings for a specific content item."""
    return db.query(models.UserItemRating).filter(
        models.UserItemRating.content_id == content_id
    ).order_by(models.UserItemRating.updated_at.desc()).all()

@router.get("/mix/{mix_id}/matrix")
def get_rating_matrix(mix_id: str, db: Session = Depends(get_db)):
    """
    Get user-item rating matrix for a mix (for collaborative filtering).
    Returns list of {user_id, content_id, rating} tuples.
    """
    ratings = db.query(models.UserItemRating).filter(
        models.UserItemRating.mix_id == mix_id
    ).all()
    
    return {
        "mix_id": mix_id,
        "ratings": [
            {
                "user_id": r.user_id,
                "content_id": r.content_id,
                "rating": float(r.rating),
                "rating_type": r.rating_type
            }
            for r in ratings
        ]
    }

@router.delete("/{rating_id}")
def delete_rating(rating_id: str, db: Session = Depends(get_db)):
    """Delete a rating."""
    rating = db.query(models.UserItemRating).filter(
        models.UserItemRating.id == rating_id
    ).first()
    
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    
    db.delete(rating)
    db.commit()
    return {"message": "Rating deleted"}
