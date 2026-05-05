"""Aggregate API v1 routers (single mount point for ``main``)."""

from fastapi import APIRouter

from app.api.v1.adaptive_ui.router import router as adaptive_ui_router
from app.api.v1.behavior.router import router as behavior_router
from app.api.v1.chat.router import router as chat_router
from app.api.v1.matching.router import router as matching_router
from app.api.v1.preferences.router import router as preferences_router
from app.api.v1.recommendations.router import router as recommendations_router
from app.api.v1.trends.router import router as trends_router
from app.api.v1.users.router import router as users_router

api_v1_router = APIRouter()

api_v1_router.include_router(
    recommendations_router,
    prefix="/recommendations",
    tags=["recommendations"],
)
api_v1_router.include_router(users_router, prefix="/users", tags=["users"])
api_v1_router.include_router(matching_router, prefix="/matching", tags=["matching"])
api_v1_router.include_router(trends_router, prefix="/trends", tags=["trends"])
api_v1_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_v1_router.include_router(
    preferences_router,
    prefix="/travel-preferences",
    tags=["travel-preferences"],
)
api_v1_router.include_router(
    behavior_router,
    prefix="/behavior-analysis",
    tags=["behavior-analysis"],
)
api_v1_router.include_router(
    adaptive_ui_router,
    prefix="/adaptive-ui",
    tags=["adaptive-ui"],
)
