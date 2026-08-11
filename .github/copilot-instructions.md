# Copilot Instructions - No-Code AI Recommendation Engine

## Architecture Overview

**FastAPI backend** serving a recommendation engine with three ML approaches, database-first data model, and business rule controls:

- **Core Stack**: FastAPI + SQLAlchemy + PostgreSQL (prod) / SQLite (dev) + scikit-learn + sentence-transformers
- **Database Tables**: `mixes` (user-created collections), `mix_contents` (items in mixes), `users`, `user_activity`, `user_item_ratings`, `watch_sessions`
- **Data Flow**: Upload CSV → Map columns → Generate semantic embeddings → Serve recommendations via `/mixes/generate-recommendations`

## Key Architectural Patterns

### Recommendation Tiers
1. **Level 1**: Basic keyword matching (fallback)
2. **Level 2**: Cosine similarity on tag-based embeddings  
3. **Level 3**: Semantic embeddings via `sentence-transformers` (cached in DB via `Embedding` table)

See [backend/mixes/generate_recommendations.py](../backend/mixes/generate_recommendations.py) — uses cosine similarity seeded from user activity or first item.

### Hybrid ML Models
`HybridRecommender` combines three trained models with configurable weights (35% collaborative, 35% sequence, 30% context):
- **Collaborative Filtering** ([collaborative_filtering.py](../backend/ml/collaborative_filtering.py)): SVD on user-item ratings; requires 5+ ratings
- **Sequence Model** ([sequence_model.py](../backend/ml/sequence_model.py)): Markov chains on watch sessions; requires 10+ sessions
- **Context Model** ([context_model.py](../backend/ml/context_model.py)): PMI-based scoring (time, device); requires 50+ interactions

Models are trained on-demand and persisted to `backend/ml/models/` as pickled objects.

### Business Rules
Applied **post-recommendation** at `general_settings` endpoint; rules filter/reorder results:
- `min_content_score`: Exclude items below threshold
- `exclude_tags` / `include_tags`: Filter by tag presence
- `boost_tags`: Amplify matching item scores
- `pinned_content_ids`: Force items to top

See [frontend/index.html](../frontend/index.html) around line 582 for UI control integration.

## Critical File Map

| Path | Purpose |
|------|---------|
| [main.py](../main.py) | FastAPI app initialization, route registration, CORS setup |
| [backend/database.py](../backend/database.py) | SQLAlchemy engine, session factory (PostgreSQL/SQLite detection) |
| [backend/models.py](../backend/models.py) | ORM models: `Mix`, `MixContent`, `UserActivity`, `UserItemRating`, `WatchSession` |
| [backend/mixes/](../backend/mixes/) | Core mix workflows: upload, map fields, generate recommendations |
| [backend/ml/](../backend/ml/) | Trained model classes + hybrid recommender |
| [backend/routes/](../backend/routes/) | API endpoints for users, activity, ratings, ML model training |

## Development Workflows

### Running Locally
```bash
# Set up venv (Python 3.9+)
python -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Database setup (auto on app startup)
python migrate_database.py  # Alembic migrations if needed

# Start FastAPI dev server
uvicorn main:app --reload --port 8000
```

### Testing
```bash
pytest tests/ -v  # See pyproject.toml for pytest config
```

### Database Migrations
- Use `alembic/env.py` to manage schema changes
- Model changes → `alembic revision --autogenerate -m "message"` → `alembic upgrade head`

## Data Collection & ML Training Workflow

1. **Collect Activity**: POST to `/user-activity` with event type, timestamp, session ID
2. **Train Models**: POST `/ml/train/{mix_id}` trains all three models on available data
3. **Get Recommendations**: GET `/mixes/generate-recommendations` with optional context (hour, device)

See [DATA_COLLECTION_GUIDE.md](../DATA_COLLECTION_GUIDE.md) and [ML_MODELS_GUIDE.md](../ML_MODELS_GUIDE.md) for full API specs.

## Codebase Conventions

**Mix Workflow Pattern** (seen in [create_mix.py](../backend/mixes/create_mix.py), [map_fields.py](../backend/mixes/map_fields.py)):
- Request validation via Pydantic schema
- DB dependency injection: `Depends(get_db)`
- Return plain dict (not ORM model) for JSON serialization
- Use `uuid.uuid4()` for ID generation

**Error Handling**:
- `HTTPException` with status code + detail message (see [generate_recommendations.py](../backend/mixes/generate_recommendations.py) line ~200)
- Avoid bare `Exception` — be specific (e.g., `FileNotFoundError`, `ValueError`)

**Embedding Caching**:
- Check `Embedding` table before recomputing (~line 130 in [generate_recommendations.py](../backend/mixes/generate_recommendations.py))
- Store vectors as binary NumPy arrays in `LargeBinary` columns; use `BytesIO` for serialization/deserialization

## Integration Points

**Auth**: Currently disabled (open-access mode). The frontend uses a local user ID stored in `localStorage` under `testUser`. The `User.supabase_user_id` column is a legacy vestige of the removed Supabase integration and is no longer written to.

**File Upload**: CSV files stored to disk in `backend/db/` with mapping metadata persisted to `FieldMapping` model

**Frontend (Vercel-hosted)**: Calls `/docs` for OpenAPI, reads API base from env, supports code samples for 10+ platforms (OTT, mobile, TV, web)

## Common Pitfalls

- **Embedding computation overhead**: Sentence-transformer loads the model on first call; cache results in DB
- **Session/transaction lifecycle**: Always use `db: Session = Depends(get_db)` in route handlers; don't create raw sessions
- **Array dtype mismatch**: NumPy arrays must be saved/loaded with `allow_pickle=False` for consistency
- **Missing minimum thresholds**: ML models fail gracefully if data is insufficient (check error dict in train response)
