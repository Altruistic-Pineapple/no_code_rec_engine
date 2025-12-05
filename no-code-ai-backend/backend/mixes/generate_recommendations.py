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

# Initialize sentence transformer for Level 3 (lazy load on first use)
_sentence_transformer_model = None

def get_sentence_transformer():
    """Lazy load the sentence transformer model on first use"""
    global _sentence_transformer_model
    if _sentence_transformer_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("DEBUG: Loading sentence-transformers model for Level 3...")
            _sentence_transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("DEBUG: Sentence-transformers model loaded successfully")
        except Exception as e:
            print(f"ERROR: Failed to load sentence-transformers: {e}")
            raise
    return _sentence_transformer_model


router = APIRouter()
@router.get("/generate-recommendations")
async def generate_recommendations(mix_id: str, user_id: str = None, content_id: str = None, top_k: int = 5, quality_level: int = None, db: Session = Depends(get_db)):
    mix_id = mix_id.strip()
    
    # Fetch mix from DB to get default quality level
    mix = db.query(MixContent).filter(MixContent.mix_id == mix_id).first()
    if not mix:
        # Try to get from Mix table if no content yet
        from backend.models import Mix
        mix = db.query(Mix).filter(Mix.id == mix_id).first()
    
    # Use provided quality_level or default to mix's quality_level
    if quality_level is None and mix:
        from backend.models import Mix
        mix_obj = db.query(Mix).filter(Mix.id == mix_id).first()
        if mix_obj:
            quality_level = int(mix_obj.quality_level)
        else:
            quality_level = 2
    elif quality_level is None:
        quality_level = 2
    
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
                "tags": r.tags,
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

    # Build the text field for similarity - include title, description, AND tags/genre
    # This ensures the LLM embeddings understand genre relationships
    title = df["title"] if "title" in df.columns else pd.Series([""] * len(df))
    desc = df["description"] if "description" in df.columns else pd.Series([""] * len(df))
    tags = df["tags"] if "tags" in df.columns else pd.Series([""] * len(df))
    
    # Repeat tags 3x to give genre more weight in the embedding
    tags_weighted = tags.fillna("").apply(lambda x: f"{x} {x} {x}" if x else "")
    df["text"] = title.fillna("") + " " + desc.fillna("") + " " + tags_weighted
    
    print(f"DEBUG: Sample text for embedding: {df['text'].iloc[0][:200] if len(df) > 0 else 'empty'}")

    if df.empty:
        raise HTTPException(400, detail="No content available")
    if (df["text"].str.strip() == "").all():
        raise HTTPException(400, detail="All text rows are empty after mapping.")

    # Handle tiny datasets
    if len(df) == 1 and content_id is None:
        return {"mix_id": mix_id, "based_on": "first_item", "recommendations": []}

    # Compute similarity based on quality level
    if quality_level == 3:
        # Level 3: Use semantic embeddings (sentence-transformers)
        print("DEBUG Level 3: Computing semantic embeddings...")
        model = get_sentence_transformer()
        texts = df["text"].fillna("").tolist()
        embeddings = model.encode(texts, show_progress_bar=False)
        sim = cosine_similarity(embeddings)
        print(f"DEBUG Level 3: Computed {len(embeddings)} semantic embeddings")
    else:
        # Level 1 & 2: Use TF-IDF
        # Clear old embeddings and recompute fresh to ensure tags/genre are included
        # This is important after algorithm updates that change the text field
        print(f"DEBUG Level {quality_level}: Computing TF-IDF with genre-weighted text...")
        
        # Always recompute TF-IDF to ensure we use the latest text (with tags)
        tfidf_sparse = TfidfVectorizer().fit_transform(df["text"])
        try:
            tfidf = tfidf_sparse.toarray()
        except Exception:
            # fallback: convert each row
            tfidf = np.vstack([row.toarray().ravel() for row in tfidf_sparse])
        sim = cosine_similarity(tfidf)
        
        print(f"DEBUG Level {quality_level}: Computed TF-IDF for {len(df)} items")

    if content_id is None:
        # If user_id provided, get their most recent watching activity
        if user_id:
            from backend.models import UserActivity
            recent_activity = db.query(UserActivity).filter(
                UserActivity.user_id == user_id,
                UserActivity.mix_id == mix_id
            ).order_by(UserActivity.timestamp.desc()).first()
            
            if recent_activity:
                content_id = recent_activity.content_id
        
        # If still no content_id, use first item
        if content_id is None:
            seed_idx = 0
        else:
            idx = df.index[df["content_id"] == content_id]
            if len(idx) == 0:
                seed_idx = 0
            else:
                seed_idx = int(idx[0])
    else:
        idx = df.index[df["content_id"] == content_id]
        if len(idx) == 0:
            raise HTTPException(404, detail="Content ID not found")
        seed_idx = int(idx[0])

    scores = sim[seed_idx]
    order = scores.argsort()[::-1]
    order = [i for i in order if i != seed_idx]
    
    # Get more items than top_k so business rules can filter/reorder
    # (pinning, exclude tags, etc. need more options to work with)
    expanded_k = max(100, top_k * 5)  # Get at least 100 or 5x top_k items
    k = max(0, min(expanded_k, len(order)))
    print(f"DEBUG: top_k={top_k}, expanded_k={expanded_k}, k={k}, len(order)={len(order)}")
    top_indices = order[:k]

    cols = [c for c in ["content_id", "title", "description", "tags"] if c in df.columns]
    recommendations = df.iloc[top_indices][cols].to_dict(orient="records")
    
    # Add scores to recommendations based on quality level
    if quality_level == 2 and user_id:
        # Level 2: Collaborative Filtering - boost items similar to what user watched
        from backend.models import UserActivity
        
        # Get items the user has already watched
        watched_items = db.query(UserActivity.content_id).filter(
            UserActivity.user_id == user_id,
            UserActivity.mix_id == mix_id
        ).all()
        watched_content_ids = set(r[0] for r in watched_items)
        print(f"DEBUG Level 2: watched_content_ids = {watched_content_ids}")
        
        # For each watched item, find its similarity to use as a boost signal
        watched_scores = {}
        for watched_id in watched_content_ids:
            watched_idx = df.index[df["content_id"] == watched_id]
            if len(watched_idx) > 0:
                watched_idx = int(watched_idx[0])
                watched_sims = sim[watched_idx]  # Similarity of watched item to ALL items
                watched_scores[watched_id] = watched_sims
        
        # Apply collaborative filtering: boost items similar to watched items
        for i, idx in enumerate(top_indices):
            tfidf_score = float(scores[idx])
            content_id_val = df.iloc[idx]["content_id"]
            
            if content_id_val in watched_content_ids:
                # Heavily demote watched items (user already saw this)
                hybrid_score = tfidf_score * 0.01
                print(f"DEBUG Level 2: {content_id_val} is watched, demoted: {tfidf_score} -> {hybrid_score}")
            else:
                # Sum similarity of this item to all watched items (collaborative boost)
                collab_boost = sum(watched_sims[idx] for watched_sims in watched_scores.values())
                # Normalize by number of watched items to keep score stable
                if watched_content_ids:
                    collab_boost = collab_boost / len(watched_content_ids)
                
                # 30% TF-IDF + 70% collaborative boost (collaborative dominates)
                hybrid_score = (tfidf_score * 0.3) + (collab_boost * 0.7)
                print(f"DEBUG Level 2: {content_id_val} TF-IDF={tfidf_score:.4f}, collab_boost={collab_boost:.4f}, hybrid={hybrid_score:.4f}")
            
            recommendations[i]["score"] = float(hybrid_score)
        
        # RE-SORT by new hybrid scores (create different ranking than Level 1)
        recommendations = sorted(recommendations, key=lambda x: x.get("score", 0), reverse=True)
        print(f"DEBUG Level 2: After re-sort = {[r.get('content_id') for r in recommendations[:5]]}")
    elif quality_level == 3 and user_id:
        # Level 3: Semantic similarity + collaborative boost (premium level)
        from backend.models import UserActivity
        
        # Get items the user has already watched
        watched_items = db.query(UserActivity.content_id).filter(
            UserActivity.user_id == user_id,
            UserActivity.mix_id == mix_id
        ).all()
        watched_content_ids = set(r[0] for r in watched_items)
        print(f"DEBUG Level 3: watched_content_ids = {watched_content_ids}")
        
        # For each watched item, get its semantic similarity to all items (collaborative signal)
        watched_scores = {}
        for watched_id in watched_content_ids:
            watched_idx = df.index[df["content_id"] == watched_id]
            if len(watched_idx) > 0:
                watched_idx = int(watched_idx[0])
                watched_sims = sim[watched_idx]  # Semantic similarity of watched item to ALL items
                watched_scores[watched_id] = watched_sims
        
        # Apply semantic similarity + collaborative boost + user history
        for i, idx in enumerate(top_indices):
            semantic_score = float(scores[idx])
            content_id_val = df.iloc[idx]["content_id"]
            
            if content_id_val in watched_content_ids:
                # Heavily demote items already watched
                hybrid_score = semantic_score * 0.01
                print(f"DEBUG Level 3: {content_id_val} is watched, demoted: {semantic_score} -> {hybrid_score}")
            else:
                # Boost items semantically similar to watched items (collaborative signal)
                collab_boost = sum(watched_sims[idx] for watched_sims in watched_scores.values())
                # Normalize by number of watched items
                if watched_content_ids:
                    collab_boost = collab_boost / len(watched_content_ids)
                
                # 80% semantic understanding + 20% collaborative boost (semantic dominates)
                hybrid_score = (semantic_score * 0.8) + (collab_boost * 0.2)
                print(f"DEBUG Level 3: {content_id_val} semantic={semantic_score:.4f}, collab_boost={collab_boost:.4f}, hybrid={hybrid_score:.4f}")
            
            recommendations[i]["score"] = float(hybrid_score)
        
        # RE-SORT by new hybrid scores (create premium ranking with both signals)
        recommendations = sorted(recommendations, key=lambda x: x.get("score", 0), reverse=True)
        print(f"DEBUG Level 3: After re-sort = {[r.get('content_id') for r in recommendations[:5]]}")
    elif quality_level == 3:
        # Level 3 without user_id: Just use semantic similarity scores
        print(f"DEBUG Level 3: Using semantic embeddings scores (no user history)")
        for i, idx in enumerate(top_indices):
            recommendations[i]["score"] = float(scores[idx])
    else:
        # Level 1: Just use TF-IDF scores
        for i, idx in enumerate(top_indices):
            recommendations[i]["score"] = float(scores[idx])
    
    # Apply business rules if they exist
    from backend.models import BusinessRules
    rules_config = db.query(BusinessRules).filter(BusinessRules.mix_id == mix_id).first()
    
    if rules_config:
        recommendations = apply_business_rules(recommendations, rules_config.rules)
    
    # NOW limit to top_k after rules are applied
    recommendations = recommendations[:top_k]
    
    # Quality level affects the response
    # 1 = Traditional ML (just return top_k)
    # 2 = Hybrid (return with scores)
    # 3 = LLM Embeddings (would require additional processing)
    response = {
        "mix_id": mix_id,
        "user_id": user_id,
        "based_on": content_id or "first_item",
        "quality_level": quality_level,
        "recommendations": recommendations
    }
    
    # For quality level 3 (LLM), we'd add additional metadata
    if quality_level == 3:
        response["method"] = "LLM Embeddings"
        response["note"] = "Using advanced semantic understanding"
    elif quality_level == 2:
        response["method"] = "Hybrid ML"
    else:
        response["method"] = "Traditional ML"

    return response


def apply_business_rules(recommendations, rules):
    """Apply business rules to filter and re-rank recommendations"""
    print(f"DEBUG apply_business_rules: input rules = {rules}")
    print(f"DEBUG apply_business_rules: input recommendations = {[r.get('content_id') for r in recommendations]}")
    
    filtered = recommendations.copy()
    
    # Filter by minimum score threshold
    if rules.get("min_content_score", 0) > 0:
        filtered = [r for r in filtered if r.get("score", 0) >= rules["min_content_score"]]
    
    # Filter by excluded tags
    exclude_tags = rules.get("exclude_tags", [])
    if exclude_tags:
        filtered = [r for r in filtered if not any(tag in r.get("tags", "") for tag in exclude_tags)]
    
    # Filter to only included tags (if specified)
    include_tags = rules.get("include_tags", [])
    if include_tags:
        filtered = [r for r in filtered if any(tag in r.get("tags", "") for tag in include_tags)]
    
    # Enforce max from same tag
    max_from_same_tag = rules.get("max_from_same_tag", 3)
    tag_counts = {}
    final = []
    for rec in filtered:
        tags = rec.get("tags", "").split(",") if rec.get("tags") else []
        added = False
        for tag in tags:
            tag = tag.strip()
            if tag not in tag_counts:
                tag_counts[tag] = 0
            if tag_counts[tag] < max_from_same_tag:
                tag_counts[tag] += 1
                if rec not in final:
                    final.append(rec)
                added = True
                break
        if not added and not tags:
            # Item has no tags, add it
            if rec not in final:
                final.append(rec)
    
    filtered = final
    
    # Boost tags in scoring
    boost_tags = rules.get("boost_tags", [])
    if boost_tags:
        for rec in filtered:
            if any(tag in rec.get("tags", "") for tag in boost_tags):
                rec["score"] = min(1.0, rec.get("score", 0) * 1.2)  # Boost by 20%
    
    # Pin content IDs at the top
    pinned_ids = rules.get("pinned_content_ids", [])
    print(f"DEBUG: pinned_ids = {pinned_ids}")
    if pinned_ids:
        pinned = []
        unpinned = []
        for rec in filtered:
            content_id = rec.get("content_id")
            print(f"DEBUG: checking {content_id} in {pinned_ids} = {content_id in pinned_ids}")
            if rec.get("content_id") in pinned_ids:
                pinned.append(rec)
            else:
                unpinned.append(rec)
        print(f"DEBUG: pinned items = {[r.get('content_id') for r in pinned]}")
        print(f"DEBUG: unpinned items = {[r.get('content_id') for r in unpinned]}")
        # Pinned items first, then others
        filtered = pinned + unpinned
        print(f"DEBUG: after pinning, filtered = {[r.get('content_id') for r in filtered]}")
    
    # Limit results
    max_results = rules.get("max_results", 10)
    filtered = filtered[:max_results]
    
    return filtered


