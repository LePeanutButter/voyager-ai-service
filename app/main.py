"""
FastAPI application for AI-powered Tourism Assistant Microservice.

This service provides:
- Personalized travel recommendations
- User profiling and preference management
- Context-aware suggestions based on location and preferences
- Traveler matching for similar interests

Architecture follows clean separation between API layer, business logic,
and ML components for maintainability and scalability.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.routes import recommendations, users, matching, trends, behavior_analysis, adaptive_ui
from app.ml.model_loader import ModelManager
from app.ml.learning_store import MatchingLearningStore
from app.services.trends_service import TrendsService
from app.services.behavior_analysis_service import BehaviorAnalysisService
from app.services.adaptive_ui_service import AdaptiveUIService
from app.chat.router import router as chat_router
from app.chat.service import ChatService
from app.preferences.router import router as travel_preferences_router
from app.preferences.service import PreferenceQuestionnaireService


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup: Load ML models and initialize components
    logger.info("Starting Tourism Assistant microservice...")
    
    # Initialize ML models
    model_manager = ModelManager()
    await model_manager.load_models()
    app.state.model_manager = model_manager

    # Continuous matching weights (PBI 27) — in-memory; persist in production
    app.state.matching_learning = MatchingLearningStore()

    # Feature 15 — predictive trends (PBI 30–31)
    trends_service = TrendsService()
    await trends_service.refresh()
    app.state.trends_service = trends_service

    # Behavior + Feature 16 — adaptive UI (comparten el mismo store in-memory)
    behavior_analysis_service = BehaviorAnalysisService(model_manager)
    app.state.behavior_analysis_service = behavior_analysis_service
    app.state.adaptive_ui_service = AdaptiveUIService(behavior_analysis_service)

    # Initialize ChatService singleton (holds in-memory conversation store)
    chat_service = ChatService()
    app.state.chat_service = chat_service
    logger.info("ChatService initialised (LLM provider: %s)", settings.LLM_PROVIDER)

    preference_questionnaire_service = PreferenceQuestionnaireService()
    app.state.preference_questionnaire_service = preference_questionnaire_service
    logger.info("PreferenceQuestionnaireService initialised")
    
    logger.info("Service startup completed successfully")
    yield
    
    # Shutdown: Cleanup resources
    logger.info("Shutting down Tourism Assistant microservice...")


# Create FastAPI application with lifespan management
app = FastAPI(
    title="Tourism Assistant API",
    description=settings.SERVICE_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(
    recommendations.router,
    prefix="/api/v1/recommendations",
    tags=["recommendations"]
)

app.include_router(
    users.router,
    prefix="/api/v1/users",
    tags=["users"]
)

app.include_router(
    matching.router,
    prefix="/api/v1/matching",
    tags=["matching"]
)

app.include_router(
    trends.router,
    prefix="/api/v1/trends",
    tags=["trends"]
)

# Chat router — AI Travel Chatbot
app.include_router(
    chat_router,
    prefix="/api/v1/chat",
    tags=["chat"]
)

app.include_router(
    travel_preferences_router,
    prefix="/api/v1/travel-preferences",
    tags=["travel-preferences"],
)

app.include_router(
    behavior_analysis.router,
    prefix="/api/v1/behavior-analysis",
    tags=["behavior-analysis"],
)

app.include_router(
    adaptive_ui.router,
    prefix="/api/v1/adaptive-ui",
    tags=["adaptive-ui"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Tourism Assistant API is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Detailed health check including ML model status."""
    try:
        model_manager = getattr(app.state, 'model_manager', None)
        models_loaded = model_manager is not None and model_manager.is_ready() if model_manager else False
        
        return {
            "status": "healthy",
            "models_loaded": models_loaded,
            "service": "tourism-assistant"
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
