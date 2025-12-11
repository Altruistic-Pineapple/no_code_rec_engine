# --- backend/schemas.py ---
from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

# Schema for creating a new user (request body)
class UserCreate(BaseModel):
    name: Optional[str] = None

# Schema for reading a user (response model)
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: Optional[str] = None
    
    @field_serializer('id')
    def serialize_id(self, value: UUID) -> str:
        return str(value)

# --- User Activity Schemas (Enhanced) ---
class UserActivityCreate(BaseModel):
    user_id: str
    mix_id: str
    content_id: Optional[str] = None
    event_type: str  # "view", "play", "like", "click", "watched", "skip", "rate"
    rating: Optional[str] = None  # For explicit ratings
    duration: Optional[str] = None  # Engagement duration in seconds
    session_id: Optional[str] = None
    sequence_order: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

class UserActivityRead(BaseModel):
    id: str
    user_id: str
    mix_id: str
    content_id: Optional[str] = None
    event_type: str
    timestamp: datetime
    rating: Optional[str] = None
    duration: Optional[str] = None
    session_id: Optional[str] = None
    sequence_order: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# --- Rating Schemas (for collaborative filtering) ---
class RatingCreate(BaseModel):
    user_id: str
    mix_id: str
    content_id: str
    rating: str  # "1" to "5" for explicit, "0.0" to "1.0" for implicit
    rating_type: str = "explicit"  # "explicit" or "implicit"

class RatingRead(BaseModel):
    id: str
    user_id: str
    mix_id: str
    content_id: str
    rating: str
    rating_type: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Watch Session Schemas (for sequence models) ---
class SessionCreate(BaseModel):
    session_id: str
    user_id: str
    mix_id: str
    device_type: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

class SessionUpdate(BaseModel):
    end_time: Optional[datetime] = None
    total_items_viewed: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

class SessionRead(BaseModel):
    id: str
    session_id: str
    user_id: str
    mix_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    device_type: Optional[str] = None
    total_items_viewed: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

# --- Batch Activity Logging ---
class BatchActivityCreate(BaseModel):
    activities: list[UserActivityCreate]

class MixRead(BaseModel):
    id: str
    title: str
    status: str
    filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
