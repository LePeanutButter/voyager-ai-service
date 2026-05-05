"""
Central FastAPI dependencies (Annotated + Depends).

Stateful services are resolved from ``app.state`` (singletons wired in lifespan).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.ml.model_loader import ModelManager
from app.modules.adaptive_ui.service import AdaptiveUIService
from app.modules.behavior.service import BehaviorAnalysisService
from app.modules.chat.service import ChatService
from app.modules.matching.service import MatchingService
from app.modules.preferences.service import PreferenceQuestionnaireService
from app.modules.recommendations.service import RecommendationService
from app.modules.trends.service import TrendsService
from app.modules.users.service import UserService


def _require_model_manager(request: Request) -> ModelManager:
    mm = getattr(request.app.state, "model_manager", None)
    if mm is None or not mm.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML models not loaded",
        )
    return mm


def get_recommendation_service(request: Request) -> RecommendationService:
    svc = getattr(request.app.state, "recommendation_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recommendation service unavailable",
        )
    return svc


def get_user_service(request: Request) -> UserService:
    svc = getattr(request.app.state, "user_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User service unavailable",
        )
    return svc


def get_matching_service(request: Request) -> MatchingService:
    svc = getattr(request.app.state, "matching_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Matching service unavailable",
        )
    return svc


def get_trends_service(request: Request) -> TrendsService:
    svc = getattr(request.app.state, "trends_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trends service not available",
        )
    return svc


def get_behavior_service(request: Request) -> BehaviorAnalysisService:
    svc = getattr(request.app.state, "behavior_analysis_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Behavior analysis service unavailable",
        )
    return svc


def get_adaptive_ui_service(request: Request) -> AdaptiveUIService:
    svc = getattr(request.app.state, "adaptive_ui_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive UI service not initialised",
        )
    return svc


def get_chat_service(request: Request) -> ChatService:
    svc: ChatService | None = getattr(request.app.state, "chat_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is not yet initialised. Please try again shortly.",
        )
    return svc


def get_preference_questionnaire_service(request: Request) -> PreferenceQuestionnaireService:
    svc: PreferenceQuestionnaireService | None = getattr(
        request.app.state, "preference_questionnaire_service", None
    )
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preference questionnaire service is unavailable",
        )
    return svc


ModelManagerDep = Annotated[ModelManager, Depends(_require_model_manager)]
RecommendationServiceDep = Annotated[RecommendationService, Depends(get_recommendation_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
MatchingServiceDep = Annotated[MatchingService, Depends(get_matching_service)]
TrendsServiceDep = Annotated[TrendsService, Depends(get_trends_service)]
BehaviorAnalysisServiceDep = Annotated[BehaviorAnalysisService, Depends(get_behavior_service)]
AdaptiveUIServiceDep = Annotated[AdaptiveUIService, Depends(get_adaptive_ui_service)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
PreferenceQuestionnaireServiceDep = Annotated[
    PreferenceQuestionnaireService,
    Depends(get_preference_questionnaire_service),
]
