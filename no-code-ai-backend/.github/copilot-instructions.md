## Quick orientation for AI coding agents

This repository is a small FastAPI-based monolith for creating and serving "mixes" (simple recommendation/content collections). Below are the critical facts, patterns, and exact examples you should use to be productive immediately.

## High-level architecture
- FastAPI app entry: `main.py` — it imports and registers routers from `backend.*` and calls `Base.metadata.create_all(bind=engine)` to ensure DB tables exist.
- App features live under `backend/`:
  - `backend/mixes/` — mix-related endpoints (feature modules). Each file typically defines an `APIRouter` and local Pydantic request models (e.g. `create_mix.py`, `upload_content.py`).
  - `backend/routes/` — cross-feature endpoints like `users` and `user_activity`.
  - `backend/models.py` — canonical SQLAlchemy model definitions (Mix, MixContent, User, UserActivity).
  - `backend/database.py` — primary SQLAlchemy engine & `get_db()` (uses `sqlite:///mixes.db`).
  - `backend/db/` — alternate DB helper (creates `test.db`) and `get_db()` — note: there are two DB modules; prefer `backend.database` + `backend.models` for the main app unless you confirm a local file explicitly expects the other.

## How the pieces communicate
- HTTP layer: FastAPI routers (`APIRouter`) in `backend/mixes/*` and `backend/routes/*`.
- DB: SQLAlchemy ORM via `get_db()` dependency. Most routes use `db.add`, `db.commit()`, `db.refresh()` patterns.
- File uploads: routes under `backend/mixes` accept multipart `UploadFile` and often parse CSV with `pandas` (see `upload_content.py`).
- Data/config: `mappings/` holds JSON mapping files; `uploads/` holds CSV samples used by upload endpoints.

## Running and debugging (exact commands)
From the project root (the folder containing `main.py`):

1. Activate the virtualenv (a `env/` directory exists in the repo):

```bash
source env/bin/activate
```

2. Install deps (if needed):

```bash
pip install -r requirements.txt
```

3. Run the server (two valid options depending on working directory):

```bash
# simple: when your cwd contains main.py
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# or use the helper script (backend/run.sh) which runs `uvicorn backend.main:app`
./backend/run.sh
```

Notes:
- `main.py` prints `route.path` at import time — this runs when Uvicorn imports the module. Use that output to confirm endpoints loaded.
- `backend/run.sh` kills processes on port 8000 and runs `uvicorn backend.main:app --reload` (so it expects module importable as `backend.main`).

## Project-specific conventions & gotchas
- Router patterns: feature files under `backend/mixes/` create an `APIRouter()` and usually define small Pydantic classes inline for request shapes (example: `MixCreateRequest` inside `backend/mixes/create_mix.py`). When adding endpoints follow that same local-schema style unless the model is shared — then add to `backend/schemas.py`.
- DB module inconsistency: some files import `backend.database.get_db()` and `backend.models` (preferred for main app), while others import `backend.db.connection.get_db()` and `backend.db.*`. Before changing DB code, search for which `get_db()` a file depends on. Prefer harmonizing to `backend.database` for production flows.
- Response modeling: handlers commonly use `response_model=` with Pydantic classes from `backend/schemas.py` and rely on `class Config: from_attributes = True` to convert SQLAlchemy models. This repo uses Pydantic v2 style (and `pydantic_core` in `requirements.txt`).
- Uploads: `backend/mixes/upload_content.py` uses `pandas.read_csv` on `UploadFile`. Large files will hold memory — consider streaming/row-wise processing for production.

## Important files to inspect when changing behavior
- `main.py` — router registration and table creation (always check this when adding new routers).
- `backend/models.py` — canonical SQLAlchemy model definitions (ensure new columns/indexes added here or via alembic migrations in `alembic/`).
- `backend/database.py` and `backend/db/connection.py` — DB engine & session factory (note the different DB file names).
- `backend/mixes/*.py` — examples of feature endpoints (see `create_mix.py`, `upload_content.py`, `map_fields.py`).
- `backend/routes/users.py`, `backend/routes/user_activity.py` — examples of user-related endpoints and use of `response_model`.

## Integration points & external deps
- Local SQLite DB files (`mixes.db` and `test.db` used in different modules).
- CSV uploads (multipart) parsed with `pandas`.
- Alembic present for migrations: `alembic.ini` and `alembic/versions/`.

## Quick examples (copyable hints)
- Create a mix endpoint is implemented at `POST /mixes/create` (see `backend/mixes/create_mix.py`). It:
  - defines `MixCreateRequest(BaseModel)`
  - uses `db = Depends(get_db)`
  - creates `models.Mix`, `db.add()`, `db.commit()`, `db.refresh()` and returns the object fields.

- Upload CSV: `backend/mixes/upload_content.py` expects a `Form` `mix_id` and a `File` field named `file` and calls `pandas.read_csv` on the uploaded content.

## What an AI agent should do first when modifying code
1. Run the app locally with the venv and confirm routes printed by `main.py`.
2. Search for `get_db()` uses to determine which DB module the files expect. If adding endpoints, pick `backend.database.get_db()` unless the file already uses the `backend.db` helpers.
3. For schema changes, update `backend/models.py` and add an Alembic migration in `alembic/versions/` when appropriate.

## Feedback & missing info
If any of these run commands or environment paths are inaccurate for your local setup (there are two `env/` folders and two DB helper modules), tell me which environment you use and I will update these instructions and harmonize DB imports as a follow-up.

---
Last updated: automated extraction. Ask for edits or to expand examples (e.g., how to add alembic migrations, tests, or CI hooks).
