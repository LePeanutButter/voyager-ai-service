"""
FastAPI application for AI-powered Tourism Assistant Microservice.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.modules.chat.service import ChatService
from app.core.config import settings
from app.ml.model_loader import ModelManager
from app.ml.learning_store import MatchingLearningStore
from app.modules.adaptive_ui.service import AdaptiveUIService
from app.modules.behavior.service import BehaviorAnalysisService
from app.modules.matching.service import MatchingService
from app.modules.preferences.service import PreferenceQuestionnaireService
from app.modules.recommendations.service import RecommendationService
from app.modules.trends.service import TrendsService
from app.modules.users.service import UserService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Tourism Assistant microservice...")

    model_manager = ModelManager()
    await model_manager.load_models()
    app.state.model_manager = model_manager

    app.state.matching_learning = MatchingLearningStore()

    trends_service = TrendsService()
    await trends_service.refresh()
    app.state.trends_service = trends_service

    behavior_analysis_service = BehaviorAnalysisService(model_manager)
    app.state.behavior_analysis_service = behavior_analysis_service
    app.state.adaptive_ui_service = AdaptiveUIService(behavior_analysis_service)

    app.state.user_service = UserService(model_manager)
    app.state.matching_service = MatchingService(model_manager, app.state.matching_learning)
    app.state.recommendation_service = RecommendationService(
        model_manager,
        trends_service=trends_service,
    )

    chat_service = ChatService()
    app.state.chat_service = chat_service
    logger.info("ChatService initialised (LLM provider: %s)", settings.LLM_PROVIDER)

    preference_questionnaire_service = PreferenceQuestionnaireService()
    app.state.preference_questionnaire_service = preference_questionnaire_service
    logger.info("PreferenceQuestionnaireService initialised")

    logger.info("Service startup completed successfully")
    yield
    logger.info("Shutting down Tourism Assistant microservice...")


app = FastAPI(
    title="Tourism Assistant API",
    description=settings.SERVICE_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Tourism Assistant API is running",
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    try:
        model_manager = getattr(app.state, "model_manager", None)
        models_loaded = (
            model_manager is not None and model_manager.is_ready() if model_manager else False
        )
        return {
            "status": "healthy",
            "models_loaded": models_loaded,
            "service": "tourism-assistant",
        }
    except Exception as e:
        logger.error("Health check failed: %s", str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
