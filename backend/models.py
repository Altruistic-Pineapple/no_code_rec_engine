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
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

# --- User record (matches Supabase schema) ---
class User(Base):
    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    supabase_user_id = Column(String, nullable=True)
    email = Column(String, nullable=True)
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
    event_type = Column(String, nullable=False)  # e.g., "view", "play", "like", "click", "watched", "skip"
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    
    # For collaborative filtering: implicit feedback strength
    rating = Column(String, nullable=True)  # Optional explicit rating (1-5)
    duration = Column(String, nullable=True)  # How long they watched/engaged (seconds)
    
    # For sequence models: session tracking
    session_id = Column(String, nullable=True, index=True)  # Group actions into sessions
    sequence_order = Column(String, nullable=True)  # Order within session
    
    # Additional context
    context_data = Column(JSON, nullable=True)  # Device, location, time of day, etc.

# Composite indexes for user activity
Index("ix_user_mix_time", UserActivity.user_id, UserActivity.mix_id, UserActivity.timestamp.desc())
Index("ix_session_sequence", UserActivity.session_id, UserActivity.sequence_order)

# --- User-Item Ratings (for collaborative filtering) ---
class UserItemRating(Base):
    __tablename__ = "user_item_ratings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    mix_id = Column(String, ForeignKey("mixes.id"), nullable=False, index=True)
    content_id = Column(String, nullable=False, index=True)
    rating = Column(String, nullable=False)  # 1-5 stars or 0-1 implicit score
    rating_type = Column(String, nullable=False, default="explicit")  # explicit or implicit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

# Unique constraint: one rating per user-item pair
Index("ix_user_content_unique", UserItemRating.user_id, UserItemRating.content_id, unique=True)

# --- Watch Sessions (for sequence models) ---
class WatchSession(Base):
    __tablename__ = "watch_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    mix_id = Column(String, ForeignKey("mixes.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, server_default=func.now())
    end_time = Column(DateTime, nullable=True)
    device_type = Column(String, nullable=True)
    total_items_viewed = Column(String, nullable=True, default="0")
    context_data = Column(JSON, nullable=True)

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
