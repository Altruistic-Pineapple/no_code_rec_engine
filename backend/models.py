from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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

# --- User record (matches Supabase schema) ---
class User(Base):
    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    supabase_user_id = Column(String, nullable=False)  # Required by Supabase
    email = Column(String, nullable=False)  # Required by Supabase
    name = Column(String(255), nullable=True)
    subscription_status = Column(String, nullable=True, server_default="inactive")
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    stripe_subscription_item_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True, server_default=func.now())

# --- User activity tracking ---
class UserActivity(Base):
    __tablename__ = "user_activity"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
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


# --- Field mappings stored in DB ---
class FieldMapping(Base):
    __tablename__ = "field_mappings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String, nullable=False, index=True)
    mappings = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, server_default=func.now(), onupdate=func.now())


# --- Business rules per mix ---
class BusinessRules(Base):
    __tablename__ = "business_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    mix_id = Column(String, nullable=False, index=True)
    rules = Column(JSON, nullable=False)  # Stores rule config as JSON
    created_at = Column(DateTime, nullable=True, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, server_default=func.now(), onupdate=func.now())
