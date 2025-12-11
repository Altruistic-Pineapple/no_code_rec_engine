"""
Context-Aware Recommendation Model
Incorporates contextual features (time, device, location) into recommendations
"""
import numpy as np
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session
from backend.models import UserActivity, MixContent
from typing import List, Dict, Optional
import pickle
import os
import json

class ContextAwareModel:
    def __init__(self, min_interactions=50):
        """
        Context-aware model using feature-based scoring
        
        Args:
            min_interactions: Minimum interactions needed to train
        """
        self.min_interactions = min_interactions
        self.context_item_scores = {}  # {context_key: {item_id: score}}
        self.item_baseline = {}  # item -> baseline popularity
        self.context_features = [
            'hour_of_day',
            'day_of_week',
            'device_type',
            'session_length'
        ]
        self.is_trained = False
        
    def extract_context(self, activity: UserActivity, context_data: Optional[dict] = None) -> Dict[str, str]:
        """
        Extract contextual features from activity
        """
        context = {}
        
        # Time-based features
        if activity.timestamp:
            dt = activity.timestamp
            context['hour_of_day'] = self._bucket_hour(dt.hour)
            context['day_of_week'] = 'weekend' if dt.weekday() >= 5 else 'weekday'
        
        # Device type from context_data
        if context_data and 'device_type' in context_data:
            context['device_type'] = context_data['device_type']
        elif activity.context_data and isinstance(activity.context_data, dict):
            context['device_type'] = activity.context_data.get('device_type', 'unknown')
        else:
            context['device_type'] = 'unknown'
        
        # Session characteristics
        if activity.duration:
            try:
                duration = int(activity.duration)
                context['session_length'] = 'long' if duration > 120 else 'short'
            except:
                context['session_length'] = 'unknown'
        else:
            context['session_length'] = 'unknown'
        
        return context
    
    def _bucket_hour(self, hour: int) -> str:
        """Group hours into time periods"""
        if 6 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 17:
            return 'afternoon'
        elif 17 <= hour < 21:
            return 'evening'
        else:
            return 'night'
    
    def train(self, db: Session, mix_id: str):
        """
        Train context-aware model by learning context-item associations
        """
        # Get all activities for this mix
        activities = db.query(UserActivity).filter(
            UserActivity.mix_id == mix_id,
            UserActivity.content_id.isnot(None)
        ).all()
        
        if len(activities) < self.min_interactions:
            raise ValueError(f"Not enough interactions. Need {self.min_interactions}, got {len(activities)}")
        
        # Count context-item co-occurrences
        context_item_counts = defaultdict(lambda: defaultdict(int))
        item_counts = defaultdict(int)
        context_counts = defaultdict(int)
        
        for activity in activities:
            context = self.extract_context(activity)
            item_id = activity.content_id
            
            # Count each context feature with item
            for feature, value in context.items():
                context_key = f"{feature}:{value}"
                context_item_counts[context_key][item_id] += 1
                context_counts[context_key] += 1
            
            item_counts[item_id] += 1
        
        # Calculate baseline item popularity
        total_interactions = len(activities)
        self.item_baseline = {
            item: count / total_interactions
            for item, count in item_counts.items()
        }
        
        # Calculate context-specific scores using lift (pointwise mutual information)
        self.context_item_scores = {}
        for context_key, items in context_item_counts.items():
            self.context_item_scores[context_key] = {}
            context_prob = context_counts[context_key] / total_interactions
            
            for item_id, count in items.items():
                item_prob = self.item_baseline[item_id]
                joint_prob = count / total_interactions
                
                # PMI: log(P(item, context) / (P(item) * P(context)))
                # Higher = stronger association
                lift = joint_prob / (item_prob * context_prob)
                self.context_item_scores[context_key][item_id] = lift
        
        self.is_trained = True
        print(f"✅ Context model trained: {len(activities)} interactions, {len(context_counts)} contexts, {len(item_counts)} items")
    
    def predict(self, context: Dict[str, str], db: Session, mix_id: str, top_k: int = 10) -> List[Dict]:
        """
        Generate recommendations given a context
        
        Args:
            context: Dict of context features {feature: value}
            db: Database session
            mix_id: Mix ID
            top_k: Number of recommendations
            
        Returns: List of {content_id, score, rank, context_relevance}
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        # Get all items for this mix
        all_items = db.query(MixContent).filter(
            MixContent.mix_id == mix_id
        ).all()
        
        item_ids = [item.content_id for item in all_items]
        
        # Score each item
        scores = {}
        for item_id in item_ids:
            # Start with baseline popularity
            score = self.item_baseline.get(item_id, 0.01)
            
            # Multiply by context-specific lift
            context_boosts = []
            for feature, value in context.items():
                context_key = f"{feature}:{value}"
                if context_key in self.context_item_scores:
                    if item_id in self.context_item_scores[context_key]:
                        lift = self.context_item_scores[context_key][item_id]
                        context_boosts.append(lift)
            
            # Apply geometric mean of context boosts
            if context_boosts:
                avg_boost = np.prod(context_boosts) ** (1.0 / len(context_boosts))
                score *= avg_boost
            
            scores[item_id] = float(score)
        
        # Sort and return top-k
        predictions = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        return [
            {
                'content_id': item,
                'score': float(score),
                'rank': idx + 1,
                'context_relevance': float(score / self.item_baseline.get(item, 0.01))
            }
            for idx, (item, score) in enumerate(predictions)
        ]
    
    def recommend(self, db: Session, user_id: str, mix_id: str, 
                   context: Optional[Dict[str, str]] = None, top_k: int = 10) -> List[Dict]:
        """
        Generate context-aware recommendations for a user
        
        Args:
            context: Optional context dict. If None, will use current time/default context
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        # If no context provided, create default from current time
        if context is None:
            now = datetime.now()
            context = {
                'hour_of_day': self._bucket_hour(now.hour),
                'day_of_week': 'weekend' if now.weekday() >= 5 else 'weekday',
                'device_type': 'web',
                'session_length': 'unknown'
            }
        
        return self.predict(context, db, mix_id, top_k)
    
    def save(self, filepath: str):
        """Save model to disk"""
        model_data = {
            'context_item_scores': {k: dict(v) for k, v in self.context_item_scores.items()},
            'item_baseline': self.item_baseline,
            'context_features': self.context_features,
            'is_trained': self.is_trained
        }
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
    
    def load(self, filepath: str):
        """Load model from disk"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.context_item_scores = defaultdict(dict, {
            k: defaultdict(float, v) 
            for k, v in model_data['context_item_scores'].items()
        })
        self.item_baseline = model_data['item_baseline']
        self.context_features = model_data['context_features']
        self.is_trained = model_data['is_trained']
