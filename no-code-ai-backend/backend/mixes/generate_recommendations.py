from fastapi import APIRouter, HTTPException, Depends
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd, json
from backend.paths import mix_csv_path, mix_mapping_path
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import MixContent, Embedding
import numpy as np
from io import BytesIO

router = APIRouter()
@router.get("/generate-recommendations")
async def generate_recommendations(mix_id: str, content_id: str = None, top_k: int = 5, db: Session = Depends(get_db)):
    mix_id = mix_id.strip()
    csv_path = mix_csv_path(mix_id)
    mapping_path = mix_mapping_path(mix_id)
    # Prefer canonical data from the DB (MixContent). This makes the DB the
    # single source of truth for recommendations. If the DB has no rows for
    # the mix, fall back to CSV + mapping on disk (legacy behavior).
    rows = (
        db.query(MixContent)
        .filter(MixContent.mix_id == mix_id)
        .all()
    )

    if rows:
        df = pd.DataFrame([
            {
                "content_id": r.content_id,
                "title": r.title,
                "description": r.description,
            }
            for r in rows
        ])
    else:
        df = None

        # Try CSV + mapping on disk (legacy flow)
        # Prefer mapping stored in DB (if migrated), otherwise fall back to file
        from backend.models import FieldMapping

        mapping = None
        try:
            fm = db.query(FieldMapping).filter(FieldMapping.mix_id == mix_id).one_or_none()
            if fm:
                mapping = fm.mappings
        except Exception:
            mapping = None

        if mapping is None and mapping_path.exists():
            try:
                with open(mapping_path) as f:
                    mapping = json.load(f)["mappings"]
            except Exception as e:
                raise HTTPException(400, detail=f"Invalid mapping JSON: {e}")

        if mapping is not None and csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
            except Exception as e:
                raise HTTPException(400, detail=f"Failed reading CSV: {e}")

            df = df.rename(columns=mapping)
        else:
            # No DB rows and no csv/mapping -> not found
            raise HTTPException(404, detail=f"Mix data or mapping not found. csv={csv_path}, mapping={mapping_path}")

    if "content_id" not in df.columns:
        raise HTTPException(400, detail="Mapped column 'content_id' is required but missing after rename.")

    title = df["title"] if "title" in df.columns else pd.Series([""] * len(df))
    desc = df["description"] if "description" in df.columns else pd.Series([""] * len(df))
    df["text"] = title.fillna("") + " " + desc.fillna("")

    if df.empty:
        raise HTTPException(400, detail="No content available")
    if (df["text"].str.strip() == "").all():
        raise HTTPException(400, detail="All text rows are empty after mapping.")

    # Handle tiny datasets
    if len(df) == 1 and content_id is None:
        return {"mix_id": mix_id, "based_on": "first_item", "recommendations": []}

    # Try to load persisted embeddings for this mix (matched by content_id)
    embeddings_rows = db.query(Embedding).filter(Embedding.mix_id == mix_id).all()

    use_persisted = False
    if embeddings_rows:
        # build a map content_id -> vector
        emb_map = {}
        try:
            for r in embeddings_rows:
                arr = np.load(BytesIO(r.vector), allow_pickle=False)
                emb_map[r.content_id] = arr
        except Exception:
            emb_map = {}

        if len(emb_map) == len(df):
            vectors = []
            all_present = True
            for _, row in df.iterrows():
                cid = row.get("content_id")
                if cid not in emb_map:
                    all_present = False
                    break
                vectors.append(emb_map[cid])

            if all_present:
                tfidf = np.vstack(vectors)
                sim = cosine_similarity(tfidf)
                use_persisted = True

    if not use_persisted:
        # compute tf-idf and persist vectors for later
        tfidf_sparse = TfidfVectorizer().fit_transform(df["text"])
        try:
            tfidf = tfidf_sparse.toarray()
        except Exception:
            # fallback: convert each row
            tfidf = np.vstack([row.toarray().ravel() for row in tfidf_sparse])
        sim = cosine_similarity(tfidf)

        # persist embeddings (overwrite existing for this mix)
        try:
            db.query(Embedding).filter(Embedding.mix_id == mix_id).delete()
            for idx, row in df.iterrows():
                vec = tfidf[idx]
                buf = BytesIO()
                np.save(buf, vec, allow_pickle=False)
                emb = Embedding(mix_id=mix_id, content_id=row.get("content_id"), vector=buf.getvalue())
                db.add(emb)
            db.commit()
        except Exception:
            db.rollback()

    if content_id is None:
        seed_idx = 0
    else:
        idx = df.index[df["content_id"] == content_id]
        if len(idx) == 0:
            raise HTTPException(404, detail="Content ID not found")
        seed_idx = int(idx[0])

    scores = sim[seed_idx]
    order = scores.argsort()[::-1]
    order = [i for i in order if i != seed_idx]
    k = max(0, min(top_k, len(order)))
    top_indices = order[:k]

    cols = [c for c in ["content_id", "title", "description"] if c in df.columns]
    recommendations = df.iloc[top_indices][cols].to_dict(orient="records")

    return {"mix_id": mix_id, "based_on": content_id or "first_item", "recommendations": recommendations}

