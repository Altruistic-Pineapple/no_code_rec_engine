# backend/paths.py
from pathlib import Path

# project root (this file is backend/paths.py -> parent is backend, parent.parent is project root)
BASE_DIR = Path(__file__).resolve().parent.parent

UPLOADS_DIR = BASE_DIR / "uploads"
MAPPINGS_DIR = BASE_DIR / "mappings"

def mix_csv_path(mix_id: str) -> Path:
    return UPLOADS_DIR / f"{mix_id}.csv"

def mix_mapping_path(mix_id: str) -> Path:
    return MAPPINGS_DIR / f"{mix_id}.json"
