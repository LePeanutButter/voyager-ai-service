"""
Configuration settings for Tourism Assistant microservice.

Centralized configuration management for different environments,
service parameters, LLM integration, and chat feature settings.
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Service configuration
    SERVICE_NAME: str = "tourism-assistant"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    SERVICE_DESCRIPTION: str = (
        "AI-powered microservice for personalized travel recommendations, "
        "conversational trip planning, traveler matching, predictive travel trends, "
        "and adaptive UI driven by behavior signals"
    )
    
    # API configuration
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080", "http://localhost:5173"]
    
    # Database configuration (placeholder for future integration)
    DATABASE_URL: str = "sqlite:///./tourism_assistant.db"
    
    # ML Model configuration
    MODEL_PATH: str = "./app/ml/models"
    RECOMMENDATION_MODEL: str = "recommendation_model.pkl"
    USER_PROFILING_MODEL: str = "user_profiling_model.pkl"
    MATCHING_MODEL: str = "traveler_matching_model.pkl"
    
    # Redis configuration (for caching - placeholder)
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 3600  # 1 hour
    
    # External API configuration (placeholder)
    WEATHER_API_KEY: str = ""
    MAPS_API_KEY: str = ""
    
    # Logging configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Recommendation engine settings
    MAX_RECOMMENDATIONS: int = 10
    SIMILARITY_THRESHOLD: float = 0.7
    DEFAULT_LOCATION_RADIUS: float = 50.0  # km
    
    # User profiling settings
    PROFILE_UPDATE_THRESHOLD: int = 5  # minimum interactions before profile update
    PREFERENCE_DECAY_FACTOR: float = 0.9  # for time-based preference weighting
    
    # Matching algorithm settings
    MAX_MATCHES: int = 20
    MIN_COMPATIBILITY_SCORE: float = 0.6
    # PBI 24: minimum destination–profile compatibility (0–1) to surface a card
    DESTINATION_MIN_COMPATIBILITY: float = 0.80

    # Feature 15 — predictive trends (PBI 30)
    TREND_ANALYSIS_WINDOW_DAYS: int = 30
    TREND_EMERGENCE_SURGE_RATIO: float = 0.50  # 50% growth vs previous window marks emerging

    # Feature 16 — adaptive UI (PBI 32–33)
    ADAPTIVE_UI_ANALYSIS_WINDOW_DAYS: int = 30
    ADAPTIVE_UI_PRIMARY_NAV_SLOTS: int = 5
    ADAPTIVE_UI_THEME_BOOST_DELTA: float = 0.12

    # -----------------------------------------------------------------------
    # LLM Integration settings
    # LLM_PROVIDER: "openai" | "openai_compatible" | "ollama" | "none"
    # Set to "none" (default) to run in rule-based fallback mode only.
    # -----------------------------------------------------------------------
    LLM_PROVIDER: str = "none"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7

    # -----------------------------------------------------------------------
    # Chat feature settings
    # -----------------------------------------------------------------------
    # Maximum messages to retain per user session (oldest evicted when exceeded)
    CHAT_MAX_HISTORY: int = 20
    # Maximum suggestions returned per chat turn
    CHAT_MAX_SUGGESTIONS: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
