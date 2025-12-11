from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.ml.hybrid_recommender import HybridRecommender
from typing import Optional

router = APIRouter(prefix="/ml", tags=["ml"])

@router.post("/train/{mix_id}")
def train_ml_models(mix_id: str, db: Session = Depends(get_db)):
    """
    Train all ML models (collaborative filtering, sequence, context) for a mix
    """
    try:
        recommender = HybridRecommender(mix_id)
        results = recommender.train_all(db)
        
        trained_count = sum(1 for v in results.values() if isinstance(v, bool) and v)
        
        return {
            "mix_id": mix_id,
            "trained_models": results,
            "success_count": trained_count,
            "message": f"Trained {trained_count}/3 models successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{mix_id}/hybrid")
def get_hybrid_recommendations(
    mix_id: str,
    user_id: str,
    top_k: int = 10,
    context_hour: Optional[str] = None,
    context_device: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get hybrid recommendations combining all ML models
    
    Args:
        mix_id: Mix ID
        user_id: User ID
        top_k: Number of recommendations
        context_hour: Time context (morning/afternoon/evening/night)
        context_device: Device type (web/mobile/tablet)
    """
    try:
        recommender = HybridRecommender(mix_id)
        
        # Try to load pre-trained models
        loaded = recommender.load_models()
        
        if not any(loaded.values()):
            raise HTTPException(
                status_code=400, 
                detail="No trained models found. Train models first using POST /ml/train/{mix_id}"
            )
        
        # Build context if provided
        context = None
        if context_hour or context_device:
            context = {}
            if context_hour:
                context['hour_of_day'] = context_hour
            if context_device:
                context['device_type'] = context_device
        
        # Get recommendations
        recommendations = recommender.recommend(
            db, user_id, context, top_k
        )
        
        return {
            "mix_id": mix_id,
            "user_id": user_id,
            "loaded_models": loaded,
            "recommendations": recommendations,
            "count": len(recommendations)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{mix_id}/collaborative")
def get_collaborative_recommendations(
    mix_id: str,
    user_id: str,
    top_k: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get recommendations from collaborative filtering only
    """
    try:
        from backend.ml.collaborative_filtering import CollaborativeFilteringModel
        
        model = CollaborativeFilteringModel()
        model.load(f"backend/ml/models/collab_{mix_id}.pkl")
        
        recommendations = model.recommend(db, user_id, mix_id, top_k)
        
        return {
            "mix_id": mix_id,
            "user_id": user_id,
            "model": "collaborative_filtering",
            "recommendations": recommendations
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model not trained yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{mix_id}/sequence")
def get_sequence_recommendations(
    mix_id: str,
    user_id: str,
    top_k: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get recommendations from sequence model only
    """
    try:
        from backend.ml.sequence_model import SequenceModel
        
        model = SequenceModel()
        model.load(f"backend/ml/models/sequence_{mix_id}.pkl")
        
        recommendations = model.recommend(db, user_id, mix_id, top_k)
        
        return {
            "mix_id": mix_id,
            "user_id": user_id,
            "model": "sequence",
            "recommendations": recommendations
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model not trained yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{mix_id}/context")
def get_context_recommendations(
    mix_id: str,
    user_id: str,
    top_k: int = 10,
    context_hour: Optional[str] = None,
    context_device: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get recommendations from context-aware model only
    """
    try:
        from backend.ml.context_model import ContextAwareModel
        
        model = ContextAwareModel()
        model.load(f"backend/ml/models/context_{mix_id}.pkl")
        
        context = {}
        if context_hour:
            context['hour_of_day'] = context_hour
        if context_device:
            context['device_type'] = context_device
        
        recommendations = model.recommend(db, user_id, mix_id, context if context else None, top_k)
        
        return {
            "mix_id": mix_id,
            "user_id": user_id,
            "model": "context_aware",
            "context": context,
            "recommendations": recommendations
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model not trained yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{mix_id}")
def get_ml_model_status(mix_id: str):
    """
    Check which ML models are trained and available for a mix
    """
    import os
    
    models_dir = "backend/ml/models"
    
    status = {
        "mix_id": mix_id,
        "models": {
            "collaborative_filtering": os.path.exists(f"{models_dir}/collab_{mix_id}.pkl"),
            "sequence": os.path.exists(f"{models_dir}/sequence_{mix_id}.pkl"),
            "context_aware": os.path.exists(f"{models_dir}/context_{mix_id}.pkl")
        }
    }
    
    status["trained_count"] = sum(1 for v in status["models"].values() if v)
    status["ready"] = status["trained_count"] > 0
    
    return status
