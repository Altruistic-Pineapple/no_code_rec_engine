# --- backend/schemas.py ---
from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional, Any
from datetime import datetime

# Schema for creating a new user (request body)
class UserCreate(BaseModel):
    name: Optional[str] = None
    supabase_user_id: Optional[str] = None  # Will be auto-generated if not provided
    email: Optional[str] = None  # Will be auto-generated if not provided

# Schema for reading a user (response model)
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    supabase_user_id: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def convert_uuid(cls, data: Any) -> Any:
        if hasattr(data, '__dict__'):
            # SQLAlchemy model - convert id to string
            result = {}
            for key in ['id', 'name', 'email', 'supabase_user_id']:
                value = getattr(data, key, None)
                result[key] = str(value) if value is not None else None
            return result
        return data
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
