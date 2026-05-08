"""Production model loader: strict artifact loading, no mock paths."""

from __future__ import annotations

import logging
import os
import pickle
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
MODEL_NOT_LOADED = "Model not loaded"


class BaseModel(ABC):
    def __init__(self, model_path: str, model_name: str):
        self.model_path = model_path
        self.model_name = model_name
        self.model: Any = None
        self.is_loaded = False
        self.metadata: Dict[str, Any] = {}

    @abstractmethod
    async def load_model(self) -> bool:
        pass

    @abstractmethod
    async def predict(self, data: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    async def validate_model(self) -> bool:
        pass

    def _load_pickle_artifact(self) -> Any:
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model artifact not found: {self.model_path}")
        with open(self.model_path, "rb") as f:
            return pickle.load(f)

    @staticmethod
    def _call_predict(artifact: Any, data: Dict[str, Any]) -> Any:
        if hasattr(artifact, "predict"):
            return artifact.predict(data)
        if callable(artifact):
            return artifact(data)
        raise RuntimeError("Loaded artifact must expose .predict(data) or be callable(data)")


class RecommendationModel(BaseModel):
    def __init__(self, model_path: str):
        super().__init__(model_path, "recommendation_model")

    async def load_model(self) -> bool:
        try:
            self.model = self._load_pickle_artifact()
            self.metadata = {
                "loaded_at": datetime.now(timezone.utc),
                "model_type": "recommendation",
                "version": "artifact",
            }
            self.is_loaded = True
            logger.info("Recommendation model loaded from %s", self.model_path)
            return True
        except Exception as e:
            logger.error("Error loading recommendation model: %s", e)
            return False

    async def predict(self, data: Dict[str, Any]) -> Any:
        if not self.is_loaded:
            raise RuntimeError(MODEL_NOT_LOADED)
        return self._call_predict(self.model, data)

    async def validate_model(self) -> bool:
        if not self.is_loaded:
            return False
        try:
            _ = await self.predict({"healthcheck": True})
            return True
        except Exception:
            return False


class UserProfilingModel(BaseModel):
    def __init__(self, model_path: str):
        super().__init__(model_path, "user_profiling_model")

    async def load_model(self) -> bool:
        try:
            self.model = self._load_pickle_artifact()
            self.metadata = {
                "loaded_at": datetime.now(timezone.utc),
                "model_type": "user_profiling",
                "version": "artifact",
            }
            self.is_loaded = True
            logger.info("User profiling model loaded from %s", self.model_path)
            return True
        except Exception as e:
            logger.error("Error loading user profiling model: %s", e)
            return False

    async def predict(self, data: Dict[str, Any]) -> Any:
        if not self.is_loaded:
            raise RuntimeError(MODEL_NOT_LOADED)
        return self._call_predict(self.model, data)

    async def validate_model(self) -> bool:
        if not self.is_loaded:
            return False
        try:
            _ = await self.predict({"healthcheck": True})
            return True
        except Exception:
            return False


class TravelerMatchingModel(BaseModel):
    def __init__(self, model_path: str):
        super().__init__(model_path, "traveler_matching_model")

    async def load_model(self) -> bool:
        try:
            self.model = self._load_pickle_artifact()
            self.metadata = {
                "loaded_at": datetime.now(timezone.utc),
                "model_type": "traveler_matching",
                "version": "artifact",
            }
            self.is_loaded = True
            logger.info("Traveler matching model loaded from %s", self.model_path)
            return True
        except Exception as e:
            logger.error("Error loading traveler matching model: %s", e)
            return False

    async def predict(self, data: Dict[str, Any]) -> Any:
        if not self.is_loaded:
            raise RuntimeError(MODEL_NOT_LOADED)
        return self._call_predict(self.model, data)

    async def validate_model(self) -> bool:
        if not self.is_loaded:
            return False
        try:
            _ = await self.predict({"healthcheck": True})
            return True
        except Exception:
            return False


class ModelManager:
    def __init__(self):
        self.models: Dict[str, BaseModel] = {}
        self.model_directory = settings.MODEL_PATH
        self.is_initialized = False

    async def load_models(self) -> bool:
        try:
            logger.info("Loading ML models...")
            os.makedirs(self.model_directory, exist_ok=True)
            models_to_load = [
                (RecommendationModel, settings.RECOMMENDATION_MODEL),
                (UserProfilingModel, settings.USER_PROFILING_MODEL),
                (TravelerMatchingModel, settings.MATCHING_MODEL),
            ]
            for model_class, model_file in models_to_load:
                model_path = os.path.join(self.model_directory, model_file)
                model = model_class(model_path)
                if await model.load_model():
                    self.models[model.model_name] = model
                    logger.info("Successfully loaded %s", model.model_name)
                else:
                    logger.error("Failed to load %s", model.model_name)
                    return False
            self.is_initialized = True
            logger.info("All ML models loaded successfully")
            return True
        except Exception as e:
            logger.error("Error loading models: %s", e)
            return False

    def get_model(self, model_name: str) -> Optional[BaseModel]:
        return self.models.get(model_name)

    def is_ready(self) -> bool:
        if not self.is_initialized:
            return False
        return all(model.is_loaded for model in self.models.values())

    async def validate_all_models(self) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        for model_name, model in self.models.items():
            try:
                results[model_name] = await model.validate_model()
            except Exception:
                results[model_name] = False
        return results

    def get_model_metadata(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for model_name, model in self.models.items():
            out[model_name] = {
                "is_loaded": model.is_loaded,
                "metadata": model.metadata,
                "model_path": model.model_path,
            }
        return out

    async def reload_model(self, model_name: str) -> bool:
        model = self.models.get(model_name)
        if not model:
            logger.error("Model %s not found", model_name)
            return False
        model.is_loaded = False
        model.model = None
        model.metadata = {}
        success = await model.load_model()
        if success:
            logger.info("Successfully reloaded %s", model_name)
        else:
            logger.error("Failed to reload %s", model_name)
        return success

    async def shutdown(self):
        await asyncio.sleep(0)
        logger.info("Shutting down model manager...")
        for model in self.models.values():
            model.is_loaded = False
        self.models.clear()
        self.is_initialized = False
        logger.info("Model manager shutdown complete")

