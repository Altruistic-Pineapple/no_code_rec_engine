# --- backend/schemas.py ---
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema for creating a new user (request body)
class UserCreate(BaseModel):
    name: str
    user_metadata: Optional[str] = None  # Optional extra data about the user

# Schema for reading a user (response model)
class UserRead(BaseModel):
    id: str
    name: str
    user_metadata: Optional[str] = None

    class Config:
        from_attributes = True  # Allows Pydantic to work with SQLAlchemy models
class UserActivityCreate(BaseModel):
    user_id: str
    mix_id: str
    event_type: str  # keep it simple; you can later validate choices

class UserActivityRead(BaseModel):
    id: str
    user_id: str
    mix_id: str
    event_type: str
    timestamp: datetime

    class Config:
        from_attributes = True

class MixRead(BaseModel):
    id: str
    title: str
    status: str
    filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
