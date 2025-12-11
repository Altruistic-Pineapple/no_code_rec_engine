"""
Hybrid Recommender System
Combines content-based, collaborative filtering, sequence, and context models
"""
from sqlalchemy.orm import Session
from backend.ml.collaborative_filtering import CollaborativeFilteringModel
from backend.ml.sequence_model import SequenceModel
from backend.ml.context_model import ContextAwareModel
from typing import List, Dict, Optional
import os

class HybridRecommender:
    def __init__(self, mix_id: str, models_dir: str = "backend/ml/models"):
        """
        Hybrid recommender that combines multiple models
        
        Args:
            mix_id: The mix ID
            models_dir: Directory to save/load trained models
        """
        self.mix_id = mix_id
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        
        self.collab_model = CollaborativeFilteringModel()
        self.sequence_model = SequenceModel()
        self.context_model = ContextAwareModel()
        
        self.model_weights = {
            'collaborative': 0.35,
            'sequence': 0.35,
            'context': 0.30
        }
        
    def train_all(self, db: Session):
        """
        Train all available models based on available data
        """
        results = {
            'collaborative': False,
            'sequence': False,
            'context': False,
            'errors': {}
        }
        
        # Try collaborative filtering
        try:
            self.collab_model.train(db, self.mix_id)
            self.collab_model.save(f"{self.models_dir}/collab_{self.mix_id}.pkl")
            results['collaborative'] = True
        except Exception as e:
            results['errors']['collaborative'] = str(e)
            print(f"⚠️  Collaborative filtering: {e}")
        
        # Try sequence model
        try:
            self.sequence_model.train(db, self.mix_id)
            self.sequence_model.save(f"{self.models_dir}/sequence_{self.mix_id}.pkl")
            results['sequence'] = True
        except Exception as e:
            results['errors']['sequence'] = str(e)
            print(f"⚠️  Sequence model: {e}")
        
        # Try context model
        try:
            self.context_model.train(db, self.mix_id)
            self.context_model.save(f"{self.models_dir}/context_{self.mix_id}.pkl")
            results['context'] = True
        except Exception as e:
            results['errors']['context'] = str(e)
            print(f"⚠️  Context model: {e}")
        
        return results
    
    def load_models(self):
        """
        Load pre-trained models from disk
        """
        loaded = {
            'collaborative': False,
            'sequence': False,
            'context': False
        }
        
        # Try loading each model
        try:
            self.collab_model.load(f"{self.models_dir}/collab_{self.mix_id}.pkl")
            loaded['collaborative'] = True
        except:
            pass
        
        try:
            self.sequence_model.load(f"{self.models_dir}/sequence_{self.mix_id}.pkl")
            loaded['sequence'] = True
        except:
            pass
        
        try:
            self.context_model.load(f"{self.models_dir}/context_{self.mix_id}.pkl")
            loaded['context'] = True
        except:
            pass
        
        return loaded
    
    def recommend(self, 
                   db: Session, 
                   user_id: str, 
                   context: Optional[Dict] = None,
                   top_k: int = 10,
                   ensemble_method: str = 'weighted') -> List[Dict]:
        """
        Generate hybrid recommendations
        
        Args:
            db: Database session
            user_id: User ID
            context: Optional context dict for context-aware model
            top_k: Number of recommendations
            ensemble_method: 'weighted' or 'rank_fusion'
            
        Returns: List of recommendations with scores
        """
        predictions = {}
        active_models = []
        
        # Get predictions from each available model
        if self.collab_model.is_trained:
            try:
                collab_preds = self.collab_model.recommend(db, user_id, self.mix_id, top_k * 3)
                for pred in collab_preds:
                    item_id = pred['content_id']
                    if item_id not in predictions:
                        predictions[item_id] = {}
                    predictions[item_id]['collaborative'] = pred['score']
                active_models.append('collaborative')
            except Exception as e:
                print(f"Collaborative filtering error: {e}")
        
        if self.sequence_model.is_trained:
            try:
                seq_preds = self.sequence_model.recommend(db, user_id, self.mix_id, top_k * 3)
                for pred in seq_preds:
                    item_id = pred['content_id']
                    if item_id not in predictions:
                        predictions[item_id] = {}
                    predictions[item_id]['sequence'] = pred['score']
                active_models.append('sequence')
            except Exception as e:
                print(f"Sequence model error: {e}")
        
        if self.context_model.is_trained:
            try:
                ctx_preds = self.context_model.recommend(db, user_id, self.mix_id, context, top_k * 3)
                for pred in ctx_preds:
                    item_id = pred['content_id']
                    if item_id not in predictions:
                        predictions[item_id] = {}
                    predictions[item_id]['context'] = pred['score']
                active_models.append('context')
            except Exception as e:
                print(f"Context model error: {e}")
        
        if not active_models:
            return []  # No models available
        
        # Combine scores
        combined_scores = []
        for item_id, scores in predictions.items():
            if ensemble_method == 'weighted':
                # Weighted average
                total_weight = 0
                combined_score = 0
                
                for model in active_models:
                    if model in scores:
                        weight = self.model_weights[model]
                        combined_score += scores[model] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    combined_score /= total_weight
            else:
                # Simple average
                model_scores = [scores.get(m, 0) for m in active_models if m in scores]
                combined_score = sum(model_scores) / len(model_scores) if model_scores else 0
            
            combined_scores.append({
                'content_id': item_id,
                'score': float(combined_score),
                'model_scores': scores,
                'models_used': active_models
            })
        
        # Sort and rank
        combined_scores.sort(key=lambda x: x['score'], reverse=True)
        
        for idx, pred in enumerate(combined_scores[:top_k]):
            pred['rank'] = idx + 1
        
        return combined_scores[:top_k]
