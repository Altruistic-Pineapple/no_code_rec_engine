# --- backend/routes/users.py ---
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db  # DB session dependency
from backend import models
from backend.schemas import UserCreate, UserRead

# Create a router for all /users endpoints
router = APIRouter(prefix="/users", tags=["users"])

# POST /users - Create a new user
@router.post("", response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    import uuid as uuid_module
    # Auto-generate required fields if not provided
    user_id = str(uuid_module.uuid4())
    supabase_user_id = payload.supabase_user_id or f"anonymous_{user_id[:8]}"
    email = payload.email or f"user_{user_id[:8]}@example.com"
    name = payload.name or f"User {user_id[:8]}"
    
    user = models.User(
        supabase_user_id=supabase_user_id,
        email=email,
        name=name
    )
    db.add(user)       # Stage new user in DB session
    db.commit()        # Save changes to DB
    db.refresh(user)   # Refresh object to get DB-generated values (like ID)
    return user

# GET /users - List all users
@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()  # Get all users from DB

# GET /users/{user_id} - Retrieve a single user by ID
@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).get(user_id)  # Look up by primary key
    if not user:
        raise HTTPException(status_code=404, detail="User not found")  # Error if no match
    return user
