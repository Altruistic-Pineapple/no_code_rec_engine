"""
Collaborative Filtering Model
Uses matrix factorization (SVD) on user-item ratings for collaborative recommendations
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy.orm import Session
from backend.models import UserItemRating, MixContent
from typing import List, Dict, Tuple
import pickle
import os

class CollaborativeFilteringModel:
    def __init__(self, n_factors=50, min_ratings=5):
        """
        Args:
            n_factors: Number of latent factors for SVD
            min_ratings: Minimum number of ratings required to train model
        """
        self.n_factors = n_factors
        self.min_ratings = min_ratings
        self.user_factors = None
        self.item_factors = None
        self.user_id_map = {}
        self.item_id_map = {}
        self.global_mean = 0.0
        self.is_trained = False
        
    def prepare_data(self, db: Session, mix_id: str) -> Tuple[csr_matrix, List[str], List[str]]:
        """
        Fetch ratings and create sparse user-item matrix
        Returns: (sparse_matrix, user_ids, item_ids)
        """
        # Get all ratings for this mix
        ratings = db.query(UserItemRating).filter(
            UserItemRating.mix_id == mix_id
        ).all()
        
        if len(ratings) < self.min_ratings:
            raise ValueError(f"Not enough ratings to train. Need at least {self.min_ratings}, got {len(ratings)}")
        
        # Build mappings
        user_ids = sorted(list(set(r.user_id for r in ratings)))
        item_ids = sorted(list(set(r.content_id for r in ratings)))
        
        self.user_id_map = {uid: idx for idx, uid in enumerate(user_ids)}
        self.item_id_map = {iid: idx for idx, iid in enumerate(item_ids)}
        
        # Build sparse matrix
        rows = []
        cols = []
        data = []
        
        for rating in ratings:
            user_idx = self.user_id_map[rating.user_id]
            item_idx = self.item_id_map[rating.content_id]
            rating_value = float(rating.rating)
            
            rows.append(user_idx)
            cols.append(item_idx)
            data.append(rating_value)
        
        matrix = csr_matrix(
            (data, (rows, cols)),
            shape=(len(user_ids), len(item_ids))
        )
        
        return matrix, user_ids, item_ids
    
    def train(self, db: Session, mix_id: str):
        """
        Train SVD model on user-item ratings
        """
        # Prepare data
        matrix, user_ids, item_ids = self.prepare_data(db, mix_id)
        
        # Calculate global mean for centering
        self.global_mean = matrix.data.mean()
        
        # Center the matrix
        matrix_centered = matrix.copy()
        matrix_centered.data = matrix_centered.data - self.global_mean
        
        # Perform SVD
        n_factors = min(self.n_factors, min(matrix.shape) - 1)
        U, sigma, Vt = svds(matrix_centered, k=n_factors)
        
        # Store factors
        self.user_factors = U
        self.item_factors = Vt.T
        self.sigma = sigma
        
        self.is_trained = True
        
        print(f"✅ Collaborative filtering trained: {len(user_ids)} users, {len(item_ids)} items, {n_factors} factors")
        
    def predict(self, user_id: str, item_id: str) -> float:
        """
        Predict rating for a user-item pair
        Returns: predicted rating (1-5 scale)
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        # Check if user/item are in training data
        if user_id not in self.user_id_map or item_id not in self.item_id_map:
            return self.global_mean  # Return global average for cold start
        
        user_idx = self.user_id_map[user_id]
        item_idx = self.item_id_map[item_id]
        
        # Predict: U * Sigma * Vt
        user_vec = self.user_factors[user_idx]
        item_vec = self.item_factors[item_idx]
        
        prediction = self.global_mean + np.dot(user_vec * self.sigma, item_vec)
        
        # Clip to valid rating range
        return np.clip(prediction, 1.0, 5.0)
    
    def recommend(self, db: Session, user_id: str, mix_id: str, top_k: int = 10) -> List[Dict]:
        """
        Generate top-k recommendations for a user
        Returns: List of {content_id, predicted_rating, rank}
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        
        # Get all items for this mix
        all_items = db.query(MixContent).filter(
            MixContent.mix_id == mix_id
        ).all()
        
        item_ids = [item.content_id for item in all_items]
        
        # Get items user hasn't rated
        user_ratings = db.query(UserItemRating).filter(
            UserItemRating.user_id == user_id,
            UserItemRating.mix_id == mix_id
        ).all()
        
        rated_item_ids = set(r.content_id for r in user_ratings)
        unrated_items = [iid for iid in item_ids if iid not in rated_item_ids]
        
        # Predict ratings for unrated items
        predictions = []
        for item_id in unrated_items:
            pred_rating = self.predict(user_id, item_id)
            predictions.append({
                'content_id': item_id,
                'predicted_rating': float(pred_rating),
                'score': float(pred_rating)
            })
        
        # Sort by predicted rating
        predictions.sort(key=lambda x: x['predicted_rating'], reverse=True)
        
        # Add rank
        for idx, pred in enumerate(predictions[:top_k]):
            pred['rank'] = idx + 1
        
        return predictions[:top_k]
    
    def save(self, filepath: str):
        """Save model to disk"""
        model_data = {
            'user_factors': self.user_factors,
            'item_factors': self.item_factors,
            'sigma': self.sigma,
            'user_id_map': self.user_id_map,
            'item_id_map': self.item_id_map,
            'global_mean': self.global_mean,
            'n_factors': self.n_factors,
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
        
        self.user_factors = model_data['user_factors']
        self.item_factors = model_data['item_factors']
        self.sigma = model_data['sigma']
        self.user_id_map = model_data['user_id_map']
        self.item_id_map = model_data['item_id_map']
        self.global_mean = model_data['global_mean']
        self.n_factors = model_data['n_factors']
        self.is_trained = model_data['is_trained']
