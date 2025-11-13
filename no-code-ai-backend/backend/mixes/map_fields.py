from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict
import os
import json
import pandas as pd

from backend.database import get_db
from sqlalchemy.orm import Session
from backend.models import MixContent, FieldMapping
from backend.models import Embedding
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from io import BytesIO

REQUIRED_FIELDS = {"title", "description", "image_url", "content_id", "tags"}

router = APIRouter()


class FieldMappingRequest(BaseModel):
    mix_id: str
    mappings: Dict[str, str]  # user_column_name -> internal_field


@router.post("/map-fields")
async def map_fields(request: FieldMappingRequest, db: Session = Depends(get_db)):
    """Save field mapping and, if a CSV exists for the mix, apply the mapping
    to populate the `mix_contents` table so downstream endpoints (like
    generate-recommendations) can read canonical data from the DB.

    Behavior:
    - Validate that all required internal fields are present in the mapping.
    - Save mapping JSON to `mappings/{mix_id}.json`.
    - If `uploads/{mix_id}.csv` exists, read it, rename columns using the
      provided mapping, delete any existing `mix_contents` rows for the mix,
      and insert the mapped rows into the DB.
    """
    mapped_fields = set(request.mappings.values())
    missing = REQUIRED_FIELDS - mapped_fields

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required internal fields: {', '.join(missing)}"
        )

    mapping_dir = "mappings"
    os.makedirs(mapping_dir, exist_ok=True)
    mapping_path = os.path.join(mapping_dir, f"{request.mix_id}.json")

    with open(mapping_path, "w") as f:
        json.dump(request.dict(), f, indent=2)

    # Persist mapping into DB (upsert)
    try:
        existing = db.query(FieldMapping).filter(FieldMapping.mix_id == request.mix_id).one_or_none()
        if existing:
            existing.mappings = request.mappings
        else:
            fm = FieldMapping(mix_id=request.mix_id, mappings=request.mappings)
            db.add(fm)
        db.commit()
    except Exception:
        db.rollback()

    # If a CSV has been uploaded for this mix, apply the mapping to populate DB
    uploads_dir = "uploads"
    csv_path = os.path.join(uploads_dir, f"{request.mix_id}.csv")
    inserted = 0
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed reading CSV: {e}")

        # Rename user columns to internal fields
        try:
            df = df.rename(columns=request.mappings)
        except Exception:
            pass

        # Ensure content_id exists after rename
        if "content_id" not in df.columns:
            raise HTTPException(status_code=400, detail="Mapped column 'content_id' is required but missing after rename.")

        # Remove existing rows for this mix to avoid duplicates
        db.query(MixContent).filter(MixContent.mix_id == request.mix_id).delete()

        # Insert new rows
        for _, row in df.iterrows():
            entry = MixContent(
                mix_id=request.mix_id,
                title=row.get("title"),
                description=row.get("description"),
                image_url=row.get("image_url"),
                content_id=row.get("content_id"),
                tags=row.get("tags"),
            )
            db.add(entry)
            inserted += 1

        db.commit()

    return {"message": "Field mapping saved", "path": mapping_path, "rows_inserted": inserted}


@router.post("/rebuild-all")
async def rebuild_all(db: Session = Depends(get_db)):
    """Re-import all mappings + CSVs and repopulate the `mix_contents` table.

    This is a convenience admin endpoint to rebuild the SQLite DB from the
    files under `mappings/` and `uploads/`. It will delete existing rows for
    each mix and insert fresh mapped rows.
    """
    mapping_dir = "mappings"
    uploads_dir = "uploads"
    results = {}

    for fname in os.listdir(mapping_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(mapping_dir, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            mix_id = data.get("mix_id") or fname.replace('.json','')
            mappings = data.get("mappings")
            if not mappings:
                results[mix_id] = {"error": "no mappings in json"}
                continue

            csv_path = os.path.join(uploads_dir, f"{mix_id}.csv")
            if not os.path.exists(csv_path):
                results[mix_id] = {"skipped": "no csv for mix"}
                continue

            # read and apply mapping
            df = pd.read_csv(csv_path)
            df = df.rename(columns=mappings)

            if "content_id" not in df.columns:
                results[mix_id] = {"error": "content_id missing after rename"}
                continue

            # replace existing rows
            db.query(MixContent).filter(MixContent.mix_id == mix_id).delete()
            inserted = 0
            for _, row in df.iterrows():
                entry = MixContent(
                    mix_id=mix_id,
                    title=row.get("title"),
                    description=row.get("description"),
                    image_url=row.get("image_url"),
                    content_id=row.get("content_id"),
                    tags=row.get("tags"),
                )
                db.add(entry)
                inserted += 1
            db.commit()
            results[mix_id] = {"inserted": inserted}

        except Exception as e:
            results[fname] = {"error": str(e)}

    return {"results": results}


@router.post("/rebuild-embeddings/{mix_id}")
async def rebuild_embeddings(mix_id: str, db: Session = Depends(get_db)):
    """Re-generate and persist TF-IDF embeddings for a single mix.

    This will prefer canonical `mix_contents` rows in the DB; if none exist
    it will fall back to `uploads/{mix_id}.csv` + mapping.
    """
    # Try DB rows first
    rows = db.query(MixContent).filter(MixContent.mix_id == mix_id).all()
    if rows:
        df = pd.DataFrame([
            {"content_id": r.content_id, "title": r.title, "description": r.description}
            for r in rows
        ])
    else:
        mapping_path = os.path.join("mappings", f"{mix_id}.json")
        csv_path = os.path.join("uploads", f"{mix_id}.csv")
        if not os.path.exists(csv_path) or not os.path.exists(mapping_path):
            raise HTTPException(status_code=404, detail="CSV or mapping not found for mix")

        try:
            with open(mapping_path) as f:
                mapping = json.load(f).get("mappings")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid mapping JSON: {e}")

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed reading CSV: {e}")

        df = df.rename(columns=mapping)

    if "content_id" not in df.columns:
        raise HTTPException(status_code=400, detail="Mapped column 'content_id' is required but missing after rename.")

    title = df["title"] if "title" in df.columns else pd.Series([""] * len(df))
    desc = df["description"] if "description" in df.columns else pd.Series([""] * len(df))
    df["text"] = title.fillna("") + " " + desc.fillna("")

    if df.empty:
        raise HTTPException(status_code=400, detail="No content available")

    # compute TF-IDF
    tfidf_sparse = TfidfVectorizer().fit_transform(df["text"])
    try:
        tfidf = tfidf_sparse.toarray()
    except Exception:
        tfidf = np.vstack([row.toarray().ravel() for row in tfidf_sparse])

    # persist embeddings
    try:
        db.query(Embedding).filter(Embedding.mix_id == mix_id).delete()
        inserted = 0
        for idx, row in df.iterrows():
            vec = tfidf[idx]
            buf = BytesIO()
            np.save(buf, vec, allow_pickle=False)
            emb = Embedding(mix_id=mix_id, content_id=row.get("content_id"), vector=buf.getvalue())
            db.add(emb)
            inserted += 1
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"mix_id": mix_id, "inserted": inserted}
