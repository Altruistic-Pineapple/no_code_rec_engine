"""
Sequence Model for Next-Item Prediction
Uses recurrent patterns in user session sequences to predict what they'll interact with next
"""
import numpy as np
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from backend.models import UserActivity, WatchSession, MixContent
from typing import List, Dict, Tuple
import pickle
import os

class SequenceModel:
    def __init__(self, sequence_length=5, min_sessions=10):
        """
        Simple sequence model using Markov chains and co-occurrence patterns
        
        Args:
            sequence_length: How many previous items to consider
            min_sessions: Minimum sessions needed to train
        """
        self.sequence_length = sequence_length
        self.min_sessions = min_sessions
        self.transition_probs = {}  # item -> {next_item: probability}
        self.item_popularity = {}  # item -> popularity score
        self.co_occurrence = {}  # (item1, item2) -> co-occurrence count
        self.is_trained = False
        
    def prepare_sequences(self, db: Session, mix_id: str) -> List[List[str]]:
        """
        Extract sequences from user sessions
        Returns: List of content_id sequences
        """
        # Get all sessions for this mix
        sessions = db.query(WatchSession).filter(
            WatchSession.mix_id == mix_id
        ).all()
        
        if len(sessions) < self.min_sessions:
            raise ValueError(f"Not enough sessions to train. Need {self.min_sessions}, got {len(sessions)}")
        
        sequences = []
        for session in sessions:
            # Get activities in this session, ordered by sequence
            activities = db.query(UserActivity).filter(
                UserActivity.session_id == session.session_id,
                UserActivity.content_id.isnot(None)
            ).order_by(UserActivity.sequence_order).all()
            
            if len(activities) >= 2:  # Need at least 2 items for a sequence
                sequence = [a.content_id for a in activities]
                sequences.append(sequence)
        
        return sequences
    
    def train(self, db: Session, mix_id: str):
        """
        Train sequence model on session data
        """
        sequences = self.prepare_sequences(db, mix_id)
        
        # Count item popularity
        all_items = []
        for seq in sequences:
            all_items.extend(seq)
        
        item_counts = Counter(all_items)
        total_items = len(all_items)
        self.item_popularity = {
            item: count / total_items 
            for item, count in item_counts.items()
        }
        
        # Build transition probabilities (1st order Markov)
        transitions = defaultdict(lambda: defaultdict(int))
        
        for sequence in sequences:
            for i in range(len(sequence) - 1):
                current_item = sequence[i]
                next_item = sequence[i + 1]
                transitions[current_item][next_item] += 1
        
        # Normalize to probabilities
        self.transition_probs = {}
        for current_item, next_items in transitions.items():
            total = sum(next_items.values())
            self.transition_probs[current_item] = {
                next_item: count / total
                for next_item, count in next_items.items()
            }
        
        # Build co-occurrence matrix (items viewed in same session)
        self.co_occurrence = defaultdict(int)
        for sequence in sequences:
            # Count all pairs in the sequence
            for i in range(len(sequence)):
                for j in range(i + 1, len(sequence)):
                    item1, item2 = sorted([sequence[i], sequence[j]])
                    self.co_occurrence[(item1, item2)] += 1
        
        self.is_trained = True
        print(f"✅ Sequence model trained: {len(sequences)} sessions, {len(self.item_popularity)} unique items")
    
    def predict_next(self, sequence: List[str], top_k: int = 10) -> List[Dict]:
        """
        Predict next items given a sequence
        
        Args:
            sequence: List of content_ids (recent history)
            top_k: Number of predictions to return
            
        Returns: List of {content_id, score, rank}
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        if not sequence:
            # No history - return popular items
            popular = sorted(
                self.item_popularity.items(),
                key=lambda x: x[1],
                reverse=True
            )[:top_k]
            
            return [
                {
                    'content_id': item,
                    'score': float(score),
                    'rank': idx + 1
                }
                for idx, (item, score) in enumerate(popular)
            ]
        
        # Score items based on transition probabilities
        scores = defaultdict(float)
        
        # Look at last N items in sequence
        recent_items = sequence[-self.sequence_length:]
        
        for item in recent_items:
            if item in self.transition_probs:
                for next_item, prob in self.transition_probs[item].items():
                    # Don't recommend items already in sequence
                    if next_item not in sequence:
                        scores[next_item] += prob
        
        # Add co-occurrence boost
        for item in recent_items:
            for (item1, item2), count in self.co_occurrence.items():
                if item1 == item and item2 not in sequence:
                    scores[item2] += count * 0.01  # Small boost
                elif item2 == item and item1 not in sequence:
                    scores[item1] += count * 0.01
        
        # Add popularity baseline for items not seen in patterns
        for item in self.item_popularity:
            if item not in sequence and item not in scores:
                scores[item] = self.item_popularity[item] * 0.1
        
        # Sort and return top-k
        predictions = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        return [
            {
                'content_id': item,
                'score': float(score),
                'rank': idx + 1
            }
            for idx, (item, score) in enumerate(predictions)
        ]
    
    def recommend(self, db: Session, user_id: str, mix_id: str, top_k: int = 10) -> List[Dict]:
        """
        Generate recommendations based on user's recent session history
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        # Get user's most recent session
        recent_session = db.query(WatchSession).filter(
            WatchSession.user_id == user_id,
            WatchSession.mix_id == mix_id
        ).order_by(WatchSession.start_time.desc()).first()
        
        if not recent_session:
            # No history - return popular items
            return self.predict_next([], top_k)
        
        # Get sequence from recent session
        activities = db.query(UserActivity).filter(
            UserActivity.session_id == recent_session.session_id,
            UserActivity.content_id.isnot(None)
        ).order_by(UserActivity.sequence_order).all()
        
        sequence = [a.content_id for a in activities]
        
        return self.predict_next(sequence, top_k)
    
    def save(self, filepath: str):
        """Save model to disk"""
        model_data = {
            'transition_probs': dict(self.transition_probs),
            'item_popularity': self.item_popularity,
            'co_occurrence': dict(self.co_occurrence),
            'sequence_length': self.sequence_length,
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
        
        self.transition_probs = defaultdict(dict, model_data['transition_probs'])
        self.item_popularity = model_data['item_popularity']
        self.co_occurrence = defaultdict(int, model_data['co_occurrence'])
        self.sequence_length = model_data['sequence_length']
        self.is_trained = model_data['is_trained']
