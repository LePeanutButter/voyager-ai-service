"""FastAPI app for the AI tourism assistant microservice.

Responsibilities:
    - Start/shutdown `lifespan`: load ML models, trends, and services into `app.state`.
    - Register CORS middleware and mount `api_v1_router` under `/api/v1`.
    - Expose root `/` and `/health` for lightweight checks.

Dependencies:
    `app.api.v1.router`, `app.core.config.settings`, domain services, and `ModelManager` in `app.ml`.
"""

from contextlib import asynccontextmanager
import asyncio
import logging
import os
from datetime import datetime, timezone
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.modules.chat.service import ChatService
from app.core.config import settings
from app.database.ai_sqlite import init_ai_sqlite
from app.db.database import check_db_connection, init_runtime_tables
from app.ml.model_loader import ModelManager
from app.ml.learning_store import MatchingLearningStore
from app.modules.adaptive_ui.service import AdaptiveUIService
from app.modules.behavior.service import BehaviorAnalysisService
from app.modules.matching.service import MatchingService
from app.modules.preferences.service import PreferenceQuestionnaireService
from app.modules.seasonality.service import SeasonalityService
from app.modules.trends.service import TrendsService
from app.modules.users.service import UserService
from app.recommendations.services.recommendation_service import RealRecommendationService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_STARTUP_STEPS = [
    "check_primary_db",
    "init_ai_sqlite",
    "load_ml_models",
    "refresh_trends",
    "init_chat",
    "init_services",
]


def _mark_startup_step(app: FastAPI, step: str, detail: str) -> None:
    status = getattr(app.state, "startup_status", None)
    if not status:
        return
    status["step"] = step
    status["detail"] = detail
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    done = int(status.get("completed_steps", 0))
    total = int(status.get("total_steps", len(_STARTUP_STEPS)))
    logger.info("[STARTUP %s/%s] %s - %s", done, total, step, detail)


def _complete_startup_step(app: FastAPI) -> None:
    status = getattr(app.state, "startup_status", None)
    if not status:
        return
    status["completed_steps"] = int(status.get("completed_steps", 0)) + 1


def _db_mode() -> str:
    url = settings.resolved_database_url
    return "postgresql" if url.startswith("postgresql") else "sqlite"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes and publishes microservice singletons on `app.state`.

    Loads models, domain services, chat, and questionnaire; on shutdown only logs.

    Args:
        app: FastAPI instance whose `state` is mutated.

    Yields:
        Control to the FastAPI runtime between startup and shutdown.
    """
    started_at = datetime.now(timezone.utc)
    startup_t0 = perf_counter()
    app.state.startup_status = {
        "ready": False,
        "started_at": started_at.isoformat(),
        "updated_at": started_at.isoformat(),
        "completed_steps": 0,
        "total_steps": len(_STARTUP_STEPS),
        "step": "boot",
        "detail": "Initializing startup sequence",
        "errors": [],
    }
    logger.info("Starting Tourism Assistant microservice...")

    try:
        _mark_startup_step(app, "check_primary_db", "Checking primary DB connectivity")
        await asyncio.to_thread(check_db_connection)
        await asyncio.to_thread(init_runtime_tables)
        _complete_startup_step(app)
        logger.info("Database connectivity OK (mode=%s)", _db_mode())
    except Exception as e:
        app.state.startup_status["errors"].append(f"check_primary_db: {e}")
        logger.error("Database check failed: %s", e)
        raise

    try:
        _mark_startup_step(app, "init_ai_sqlite", "Initializing AI SQLite storage")
        init_ai_sqlite()
        _complete_startup_step(app)
        logger.info("AI SQLite connectivity OK")
    except Exception as e:
        app.state.startup_status["errors"].append(f"init_ai_sqlite: {e}")
        logger.error("AI DB init failed: %s", e)
        raise

    _mark_startup_step(app, "load_ml_models", "Loading ML models")
    model_manager = ModelManager()
    await model_manager.load_models()
    _complete_startup_step(app)
    app.state.model_manager = model_manager

    app.state.matching_learning = MatchingLearningStore()

    _mark_startup_step(app, "refresh_trends", "Refreshing trends data")
    trends_service = TrendsService()
    await trends_service.refresh()
    _complete_startup_step(app)
    app.state.trends_service = trends_service

    behavior_analysis_service = BehaviorAnalysisService(model_manager)
    app.state.behavior_analysis_service = behavior_analysis_service
    app.state.adaptive_ui_service = AdaptiveUIService(behavior_analysis_service)

    app.state.user_service = UserService(model_manager)
    app.state.matching_service = MatchingService(model_manager, app.state.matching_learning)

    seasonality_service = SeasonalityService()
    app.state.seasonality_service = seasonality_service

    _mark_startup_step(app, "init_chat", "Initializing chat service")
    chat_service = ChatService()
    app.state.chat_service = chat_service
    _complete_startup_step(app)
    logger.info("ChatService initialised (LLM provider: %s)", settings.LLM_PROVIDER)

    _mark_startup_step(app, "init_services", "Initializing local AI services")
    app.state.real_recommendation_service = RealRecommendationService()
    try:
        from app.ai.chatbot.service import LocalSpanishChatbotService

        app.state.local_chatbot_service = LocalSpanishChatbotService()
        logger.info("LocalSpanishChatbotService inicializado")
    except Exception as chat_exc:  # ImportError/OSError DLL, modelos HF, etc.
        app.state.local_chatbot_service = None
        logger.warning(
            "Chatbot local deshabilitado (%s); revisa Ollama, deps ML o logs del contenedor. "
            "Rutas /api/v1/local/chat* responderán 503.",
            chat_exc,
        )

    preference_questionnaire_service = PreferenceQuestionnaireService()
    app.state.preference_questionnaire_service = preference_questionnaire_service
    _complete_startup_step(app)
    logger.info("PreferenceQuestionnaireService initialised")

    elapsed = round(perf_counter() - startup_t0, 2)
    app.state.startup_status.update(
        {
            "ready": True,
            "step": "ready",
            "detail": "Startup completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "ready_in_seconds": elapsed,
        }
    )
    logger.info("Service startup completed successfully")
    logger.info("SERVICE_READY host=%s port=%s startup_seconds=%.2f", "127.0.0.1", 8000, elapsed)
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

_cors_kwargs = {
    "allow_origins": settings.allowed_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
_cors_regex = settings.resolved_cors_origin_regex
if _cors_regex:
    _cors_kwargs["allow_origin_regex"] = _cors_regex
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Returns a minimal payload confirming the API is running.

    Returns:
        dict: Message, version, and status text.
    """
    return {
        "message": "Tourism Assistant API is running",
        "version": "1.0.0",
        "status": "healthy",
    }


@app.get(
    "/health",
    responses={
        503: {
            "description": "Service unavailable",
            "content": {"application/json": {"example": {"detail": "Service unavailable"}}},
        }
    },
)
async def health_check():
    """Checks process availability and whether ML models report ready.

    Returns:
        dict: `status`, `models_loaded`, and service name.

    Raises:
        HTTPException: 503 if the check fails unexpectedly.
    """
    try:
        model_manager = getattr(app.state, "model_manager", None)
        models_loaded = (
            model_manager is not None and model_manager.is_ready() if model_manager else False
        )
        try:
            await asyncio.to_thread(check_db_connection)
        except Exception as db_err:
            logger.warning("Health: database check failed: %s", db_err)
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "database": "error",
                    "models_loaded": models_loaded,
                    "service": "tourism-assistant",
                },
            )
        return {
            "status": "healthy",
            "database": "ok",
            "models_loaded": models_loaded,
            "service": "tourism-assistant",
        }
    except Exception as e:
        logger.error("Health check failed: %s", str(e))
        raise HTTPException(status_code=503, detail="Service unavailable")


if __name__ == "__main__":
    import uvicorn

    # Default to localhost for safer local execution; override in deployment if needed.
    bind_host = os.getenv("UVICORN_HOST", "127.0.0.1")
    uvicorn.run(
        "app.main:app",
        host=bind_host,
        port=8000,
        reload=True,
        log_level="info",
    )
