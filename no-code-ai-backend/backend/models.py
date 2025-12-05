from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Index, LargeBinary
from sqlalchemy.sql import func
from backend.database import Base
import uuid

# --- Mix metadata (created by user) ---
class Mix(Base):
    __tablename__ = "mixes"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=True, index=True)  # Owner of this mix (Supabase user ID)
    title = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=True)
    quality_level = Column(String, nullable=False, default="2")  # Default to Level 2
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

# --- User record ---
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    user_metadata = Column("metadata", JSON, nullable=True)  # optional

# --- User activity tracking ---
class UserActivity(Base):
    __tablename__ = "user_activity"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    mix_id = Column(String, ForeignKey("mixes.id"), nullable=False, index=True)
    content_id = Column(String, nullable=True, index=True)  # Content that was viewed
    event_type = Column(String, nullable=False)  # e.g., "view", "play", "like"
    timestamp = Column(DateTime, nullable=False, server_default=func.now())

# Composite index for user activity
Index("ix_user_mix_time", UserActivity.user_id, UserActivity.mix_id, UserActivity.timestamp.desc())

# --- Uploaded content tied to a mix (one row per item) ---
class MixContent(Base):
    __tablename__ = "mix_contents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String, ForeignKey("mixes.id"), nullable=False, index=True)

    title = Column(String)
    description = Column(String)
    image_url = Column(String)
    content_id = Column(String)
    tags = Column(String)


# --- Persisted embeddings for items (optional acceleration)
class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String, ForeignKey("mixes.id"), nullable=False, index=True)
    content_id = Column(String, nullable=False, index=True)
    # store vector as compact binary blob (numpy .npy bytes)
    vector = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


# --- Field mappings stored in DB (optional) ---
class FieldMapping(Base):
    __tablename__ = "field_mappings"

    mix_id = Column(String, primary_key=True, index=True)
    mappings = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), index=True)


# --- Business rules per mix ---
class BusinessRules(Base):
    __tablename__ = "business_rules"

    mix_id = Column(String, primary_key=True, index=True)
    rules = Column(JSON, nullable=False)  # Stores rule config as JSON
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), index=True)
