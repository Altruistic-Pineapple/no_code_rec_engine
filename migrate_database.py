"""
Database Migration Script
Adds new columns and tables for collaborative filtering and sequence models
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env file")
    exit(1)

print(f"Connecting to database...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("✅ Connected successfully")
    print("\nRunning migrations...")
    
    # Add new columns to user_activity table
    print("  - Adding columns to user_activity...")
    cur.execute("""
        ALTER TABLE user_activity 
        ADD COLUMN IF NOT EXISTS rating VARCHAR,
        ADD COLUMN IF NOT EXISTS duration VARCHAR,
        ADD COLUMN IF NOT EXISTS session_id VARCHAR,
        ADD COLUMN IF NOT EXISTS sequence_order VARCHAR,
        ADD COLUMN IF NOT EXISTS context_data JSON;
    """)
    
    # Create indexes
    print("  - Creating indexes...")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_user_activity_session_id ON user_activity(session_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_session_sequence ON user_activity(session_id, sequence_order);")
    
    # Create user_item_ratings table
    print("  - Creating user_item_ratings table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_item_ratings (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            mix_id VARCHAR NOT NULL,
            content_id VARCHAR NOT NULL,
            rating VARCHAR NOT NULL,
            rating_type VARCHAR NOT NULL DEFAULT 'explicit',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS ix_user_item_ratings_user_id ON user_item_ratings(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_user_item_ratings_mix_id ON user_item_ratings(mix_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_user_item_ratings_content_id ON user_item_ratings(content_id);")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_content_unique ON user_item_ratings(user_id, content_id);")
    
    # Create watch_sessions table
    print("  - Creating watch_sessions table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS watch_sessions (
            id VARCHAR PRIMARY KEY,
            session_id VARCHAR NOT NULL UNIQUE,
            user_id VARCHAR NOT NULL,
            mix_id VARCHAR NOT NULL,
            start_time TIMESTAMP NOT NULL DEFAULT NOW(),
            end_time TIMESTAMP,
            device_type VARCHAR,
            total_items_viewed VARCHAR DEFAULT '0',
            context_data JSON
        );
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS ix_watch_sessions_session_id ON watch_sessions(session_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_watch_sessions_user_id ON watch_sessions(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_watch_sessions_mix_id ON watch_sessions(mix_id);")
    
    # Commit changes
    conn.commit()
    
    print("\n✅ Migration completed successfully!")
    print("\nNew tables created:")
    print("  - user_item_ratings (for collaborative filtering)")
    print("  - watch_sessions (for sequence models)")
    print("\nNew columns added to user_activity:")
    print("  - rating, duration, session_id, sequence_order, context_data")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    exit(1)
