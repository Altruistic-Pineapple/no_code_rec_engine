# Compatibility wrapper: re-export the main DB helpers from `backend.database`.
# This keeps older imports like `backend.db.connection.get_db` working while
# centralizing the actual DB configuration in `backend/database.py`.
from backend.database import engine, SessionLocal, Base, get_db
