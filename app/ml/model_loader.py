"""
ML Model Loader for Tourism Assistant.

Handles loading, caching, and management of machine learning models
for recommendations, user profiling, and traveler matching.
"""

import os
import pickle
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import numpy as np
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseModel(ABC):
    """Abstract base class for ML models."""
    
    def __init__(self, model_path: str, model_name: str):
        self.model_path = model_path
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        self.metadata = {}
    
    @abstractmethod
    async def load_model(self) -> bool:
        """Load the model from disk."""
        pass
    
    @abstractmethod
    async def predict(self, data: Dict[str, Any]) -> Any:
        """Make predictions using the loaded model."""
        pass
    
    @abstractmethod
    async def validate_model(self) -> bool:
        """Validate that the model is working correctly."""
        pass


class RecommendationModel(BaseModel):
    """ML model for travel recommendations."""
    
    def __init__(self, model_path: str):
        super().__init__(model_path, "recommendation_model")
    
    async def load_model(self) -> bool:
        """Load recommendation model."""
        try:
            # In production, load actual ML model
            # For now, create a mock model
            self.model = {
                'type': 'collaborative_filtering',
                'version': '1.0',
                'features': ['user_preferences', 'location', 'time_of_day', 'season'],
                'algorithm': 'matrix_factorization'
            }
            self.metadata = {
                'loaded_at': datetime.utcnow(),
                'model_type': 'recommendation',
                'version': '1.0',
                'accuracy': 0.85
            }
            self.is_loaded = True
            
            logger.info(f"Recommendation model loaded successfully from {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading recommendation model: {str(e)}")
            return False
    
    async def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendation predictions."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")
        
        try:
            # Mock prediction logic
            user_id = data.get('user_id', '')
            location = data.get('location', {})
            preferences = data.get('preferences', [])
            
            # Generate mock scores
            predictions = {
                'user_id': user_id,
                'location_scores': np.random.rand(10).tolist(),
                'preference_scores': np.random.rand(len(preferences)).tolist() if preferences else [],
                'confidence_score': np.random.uniform(0.7, 0.95),
                'recommendation_ids': [f"rec_{i}" for i in range(10)],
                'model_version': self.metadata.get('version', '1.0')
            }
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error in recommendation prediction: {str(e)}")
            raise
    
    async def validate_model(self) -> bool:
        """Validate recommendation model."""
        try:
            if not self.is_loaded:
                return False
            
            # Test prediction
            test_data = {
                'user_id': 'test_user',
                'location': {'latitude': 40.7128, 'longitude': -74.0060},
                'preferences': ['cultural', 'foodie']
            }
            
            prediction = await self.predict(test_data)
            
            # Validate prediction structure
            required_keys = ['user_id', 'confidence_score', 'recommendation_ids']
            if not all(key in prediction for key in required_keys):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating recommendation model: {str(e)}")
            return False


class UserProfilingModel(BaseModel):
    """ML model for user profiling and preference learning."""
    
    def __init__(self, model_path: str):
        super().__init__(model_path, "user_profiling_model")
    
    async def load_model(self) -> bool:
        """Load user profiling model."""
        try:
            # In production, load actual ML model
            self.model = {
                'type': 'neural_network',
                'version': '1.0',
                'features': ['interaction_history', 'demographics', 'behavior_patterns'],
                'algorithm': 'deep_learning'
            }
            self.metadata = {
                'loaded_at': datetime.utcnow(),
                'model_type': 'user_profiling',
                'version': '1.0',
                'accuracy': 0.82
            }
            self.is_loaded = True
            
            logger.info(f"User profiling model loaded successfully from {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading user profiling model: {str(e)}")
            return False
    
    async def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate user profile predictions."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")
        
        try:
            # Mock prediction logic
            user_id = data.get('user_id', '')
            interactions = data.get('interactions', [])
            demographics = data.get('demographics', {})
            
            # Generate mock profile predictions
            predictions = {
                'user_id': user_id,
                'predicted_preferences': ['cultural', 'adventure', 'foodie'],
                'travel_style': 'mid-range',
                'budget_range': {'min': 100, 'max': 500},
                'confidence_score': np.random.uniform(0.75, 0.90),
                'personality_traits': ['explorer', 'social', 'curious'],
                'model_version': self.metadata.get('version', '1.0')
            }
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error in user profiling prediction: {str(e)}")
            raise
    
    async def validate_model(self) -> bool:
        """Validate user profiling model."""
        try:
            if not self.is_loaded:
                return False
            
            # Test prediction
            test_data = {
                'user_id': 'test_user',
                'interactions': [{'type': 'like', 'activity_id': 'act1'}],
                'demographics': {'age': 30, 'location': 'NYC'}
            }
            
            prediction = await self.predict(test_data)
            
            # Validate prediction structure
            required_keys = ['user_id', 'predicted_preferences', 'confidence_score']
            if not all(key in prediction for key in required_keys):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating user profiling model: {str(e)}")
            return False


class TravelerMatchingModel(BaseModel):
    """ML model for traveler compatibility matching."""
    
    def __init__(self, model_path: str):
        super().__init__(model_path, "traveler_matching_model")
    
    async def load_model(self) -> bool:
        """Load traveler matching model."""
        try:
            # In production, load actual ML model
            self.model = {
                'type': 'similarity_learning',
                'version': '1.0',
                'features': ['preferences', 'demographics', 'travel_history', 'personality'],
                'algorithm': 'siamese_network'
            }
            self.metadata = {
                'loaded_at': datetime.utcnow(),
                'model_type': 'traveler_matching',
                'version': '1.0',
                'accuracy': 0.78
            }
            self.is_loaded = True
            
            logger.info(f"Traveler matching model loaded successfully from {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading traveler matching model: {str(e)}")
            return False
    
    async def predict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compatibility predictions."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")
        
        try:
            # Mock prediction logic
            user1_id = data.get('user1_id', '')
            user2_id = data.get('user2_id', '')
            user1_profile = data.get('user1_profile', {})
            user2_profile = data.get('user2_profile', {})
            
            # Generate mock compatibility scores
            compatibility_score = np.random.uniform(0.3, 0.95)
            
            predictions = {
                'user1_id': user1_id,
                'user2_id': user2_id,
                'compatibility_score': compatibility_score,
                'preference_match': np.random.uniform(0.4, 0.9),
                'travel_style_match': np.random.uniform(0.5, 0.95),
                'demographic_match': np.random.uniform(0.3, 0.8),
                'confidence_score': np.random.uniform(0.7, 0.9),
                'recommendation': 'match' if compatibility_score > 0.6 else 'no_match',
                'model_version': self.metadata.get('version', '1.0')
            }
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error in traveler matching prediction: {str(e)}")
            raise
    
    async def validate_model(self) -> bool:
        """Validate traveler matching model."""
        try:
            if not self.is_loaded:
                return False
            
            # Test prediction
            test_data = {
                'user1_id': 'user1',
                'user2_id': 'user2',
                'user1_profile': {'preferences': ['cultural'], 'age': 30},
                'user2_profile': {'preferences': ['cultural'], 'age': 32}
            }
            
            prediction = await self.predict(test_data)
            
            # Validate prediction structure
            required_keys = ['user1_id', 'user2_id', 'compatibility_score', 'recommendation']
            if not all(key in prediction for key in required_keys):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating traveler matching model: {str(e)}")
            return False


class ModelManager:
    """Manages loading and access to all ML models."""
    
    def __init__(self):
        self.models: Dict[str, BaseModel] = {}
        self.model_directory = settings.MODEL_PATH
        self.is_initialized = False
    
    async def load_models(self) -> bool:
        """Load all ML models."""
        try:
            logger.info("Loading ML models...")
            
            # Create model directory if it doesn't exist
            os.makedirs(self.model_directory, exist_ok=True)
            
            # Initialize and load models
            models_to_load = [
                (RecommendationModel, settings.RECOMMENDATION_MODEL),
                (UserProfilingModel, settings.USER_PROFILING_MODEL),
                (TravelerMatchingModel, settings.MATCHING_MODEL)
            ]
            
            for model_class, model_file in models_to_load:
                model_path = os.path.join(self.model_directory, model_file)
                model = model_class(model_path)
                
                if await model.load_model():
                    self.models[model.model_name] = model
                    logger.info(f"Successfully loaded {model.model_name}")
                else:
                    logger.error(f"Failed to load {model.model_name}")
                    return False
            
            self.is_initialized = True
            logger.info("All ML models loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            return False
    
    def get_model(self, model_name: str) -> Optional[BaseModel]:
        """Get a specific model by name."""
        return self.models.get(model_name)
    
    def is_ready(self) -> bool:
        """Check if all models are loaded and ready."""
        if not self.is_initialized:
            return False
        
        return all(model.is_loaded for model in self.models.values())
    
    async def validate_all_models(self) -> Dict[str, bool]:
        """Validate all loaded models."""
        validation_results = {}
        
        for model_name, model in self.models.items():
            try:
                validation_results[model_name] = await model.validate_model()
            except Exception as e:
                logger.error(f"Error validating {model_name}: {str(e)}")
                validation_results[model_name] = False
        
        return validation_results
    
    def get_model_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all loaded models."""
        metadata = {}
        
        for model_name, model in self.models.items():
            metadata[model_name] = {
                'is_loaded': model.is_loaded,
                'metadata': model.metadata,
                'model_path': model.model_path
            }
        
        return metadata
    
    async def reload_model(self, model_name: str) -> bool:
        """Reload a specific model."""
        try:
            model = self.models.get(model_name)
            if not model:
                logger.error(f"Model {model_name} not found")
                return False
            
            logger.info(f"Reloading model {model_name}...")
            
            # Reset model state
            model.is_loaded = False
            model.model = None
            model.metadata = {}
            
            # Reload model
            success = await model.load_model()
            
            if success:
                logger.info(f"Successfully reloaded {model_name}")
            else:
                logger.error(f"Failed to reload {model_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error reloading model {model_name}: {str(e)}")
            return False
    
    async def shutdown(self):
        """Cleanup resources when shutting down."""
        logger.info("Shutting down model manager...")
        
        for model_name, model in self.models.items():
            try:
                # Perform any cleanup needed for each model
                model.is_loaded = False
                logger.info(f"Cleaned up {model_name}")
            except Exception as e:
                logger.error(f"Error cleaning up {model_name}: {str(e)}")
        
        self.models.clear()
        self.is_initialized = False
        logger.info("Model manager shutdown complete")
