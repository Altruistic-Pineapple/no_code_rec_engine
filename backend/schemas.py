# --- backend/schemas.py ---
from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Optional
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
class UserActivityCreate(BaseModel):
    user_id: str
    mix_id: str
    content_id: Optional[str] = None  # Content that was viewed
    event_type: str  # keep it simple; you can later validate choices

class UserActivityRead(BaseModel):
    id: str
    user_id: str
    mix_id: str
    content_id: Optional[str] = None
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
