from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# The SQLite database file
DATABASE_URL = "sqlite:///mixes.db"

# Create the engine for connecting to the SQLite DB
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create the session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Base class to define models
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()