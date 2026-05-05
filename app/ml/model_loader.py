"""In-memory load and management of ML models for the tourism assistant.

Purpose:
    Initialize recommendation, profiling, and matching models; validate them; expose metadata.

Responsibilities:
    Create artifact directory, load mock or real instances, selective reload, and shutdown.

Dependencies:
    ``numpy``, ``app.core.config.settings`` (paths and file names).
"""

import os
import pickle
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import numpy as np
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseModel(ABC):
    """Minimal contract for asynchronously loadable models.

    Important attributes:
        model_path: Expected on-disk artifact path.
        model_name: Logical key of the model in the manager.
        model: Internal object or dict after load.
        is_loaded: Availability flag for inference.
        metadata: Version metadata and optional metrics.
    """

    def __init__(self, model_path: str, model_name: str):
        self.model_path = model_path
        self.model_name = model_name
        self.model = None
        self.is_loaded = False
        self.metadata = {}
    
    @abstractmethod
    async def load_model(self) -> bool:
        """Loads the artifact from disk or initializes a mock.

        Returns:
            ``True`` if load succeeded.
        """
        pass

    @abstractmethod
    async def predict(self, data: Dict[str, Any]) -> Any:
        """Runs inference on a structured payload.

        Args:
            data: Inputs expected by the concrete model.

        Returns:
            Serializable output (dict or other).

        Raises:
            RuntimeError: If the model is not loaded.
        """
        pass

    @abstractmethod
    async def validate_model(self) -> bool:
        """Runs a test prediction and checks output shape.

        Returns:
            ``True`` if internal validation passes.
        """
        pass


class RecommendationModel(BaseModel):
    """Mock recommendation model from preferences and location."""

    def __init__(self, model_path: str):
        super().__init__(model_path, "recommendation_model")
    
    async def load_model(self) -> bool:
        """Initializes a mock collaborative-filtering structure.

        Returns:
            ``True`` unless an uncaught exception occurs (then ``False``).
        """
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
                'loaded_at': datetime.now(timezone.utc),
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
        """Generates mock scores and recommendation ids.

        Args:
            data: Should include at least ``user_id``, ``location``, ``preferences``.

        Returns:
            Dict with scores, confidence, and synthetic ids.

        Raises:
            RuntimeError: If ``is_loaded`` is false.
        """
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
        """Checks that a test prediction contains required keys.

        Returns:
            ``False`` if not loaded, keys missing, or an error occurs.
        """
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
    """Mock model inferring preferences and style from interactions."""

    def __init__(self, model_path: str):
        super().__init__(model_path, "user_profiling_model")
    
    async def load_model(self) -> bool:
        """Initializes a mock neural-network descriptor for profiling.

        Returns:
            ``True`` if initialization completes without logged error.
        """
        try:
            # In production, load actual ML model
            self.model = {
                'type': 'neural_network',
                'version': '1.0',
                'features': ['interaction_history', 'demographics', 'behavior_patterns'],
                'algorithm': 'deep_learning'
            }
            self.metadata = {
                'loaded_at': datetime.now(timezone.utc),
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
        """Returns simulated preferences and traits for a user.

        Args:
            data: Typically ``user_id``, ``interactions``, ``demographics``.

        Returns:
            Predicted profile with budget ranges and random confidence.

        Raises:
            RuntimeError: If the model is not loaded.
        """
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
        """Validates minimal structure of ``predict`` output.

        Returns:
            ``True`` only if required keys are present.
        """
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
        """Initializes a mock similarity-learning descriptor.

        Returns:
            ``True`` if mock load completes successfully.
        """
        try:
            # In production, load actual ML model
            self.model = {
                'type': 'similarity_learning',
                'version': '1.0',
                'features': ['preferences', 'demographics', 'travel_history', 'personality'],
                'algorithm': 'siamese_network'
            }
            self.metadata = {
                'loaded_at': datetime.now(timezone.utc),
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
        """Computes mock compatibility score and binary recommendation.

        Args:
            data: Profiles and ids for both users.

        Returns:
            Dict with sub-scores and ``match`` / ``no_match`` label.

        Raises:
            RuntimeError: If no model is loaded.
        """
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
        """Checks that mock prediction includes ids and compatibility score.

        Returns:
            ``True`` if key checks succeed.
        """
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
    """Orchestrates load, validation, and reload of all registered models.

    Important attributes:
        models: Logical name → ``BaseModel`` instance map.
        model_directory: Base directory from ``settings.MODEL_PATH``.
        is_initialized: Whether ``load_models`` completed successfully.
    """

    def __init__(self):
        self.models: Dict[str, BaseModel] = {}
        self.model_directory = settings.MODEL_PATH
        self.is_initialized = False
    
    async def load_models(self) -> bool:
        """Creates the model directory and loads recommendation, profiling, and matching.

        Returns:
            ``False`` if any sub-load fails; ``True`` if all succeed.
        """
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
        """Returns a loaded instance by logical key.

        Args:
            model_name: For example ``recommendation_model``.

        Returns:
            Instance or ``None`` if not registered.
        """
        return self.models.get(model_name)

    def is_ready(self) -> bool:
        """Checks initialization and each model's ``is_loaded`` flag.

        Returns:
            ``True`` only if the manager is initialized and all models are loaded.
        """
        if not self.is_initialized:
            return False
        
        return all(model.is_loaded for model in self.models.values())
    
    async def validate_all_models(self) -> Dict[str, bool]:
        """Runs ``validate_model`` logically in parallel (sequential in code).

        Returns:
            Map of name → validation success.
        """
        validation_results = {}
        
        for model_name, model in self.models.items():
            try:
                validation_results[model_name] = await model.validate_model()
            except Exception as e:
                logger.error(f"Error validating {model_name}: {str(e)}")
                validation_results[model_name] = False
        
        return validation_results
    
    def get_model_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Exposes load state, internal metadata, and path per model."""
        metadata = {}
        
        for model_name, model in self.models.items():
            metadata[model_name] = {
                'is_loaded': model.is_loaded,
                'metadata': model.metadata,
                'model_path': model.model_path
            }
        
        return metadata
    
    async def reload_model(self, model_name: str) -> bool:
        """Resets state and calls ``load_model`` again for a given name.

        Args:
            model_name: Key in ``self.models``.

        Returns:
            Boolean reload result or ``False`` if the model does not exist.
        """
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
        """Marks models unloaded, clears the registry, and resets the manager."""
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
