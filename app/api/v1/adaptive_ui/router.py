"""Feature 16 — adaptive UI (menu + home feed)."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdaptiveUIServiceDep
from app.modules.adaptive_ui.schemas import HomeFeedLayoutResponse, MenuAdaptationResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/menu/{user_id}",
    response_model=MenuAdaptationResponse,
    summary="Reorganización inteligente de menú (PBI 32)",
)
def get_adaptive_menu(user_id: str, service: AdaptiveUIServiceDep):
    try:
        return service.build_menu_adaptation(user_id)
    except Exception as e:
        logger.error("adaptive menu: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error building menu adaptation",
        ) from e


@router.get(
    "/home-feed/{user_id}",
    response_model=HomeFeedLayoutResponse,
    summary="Contenido dinámico de pantalla principal (PBI 33)",
)
def get_adaptive_home_feed(user_id: str, service: AdaptiveUIServiceDep):
    try:
        return service.build_home_feed_layout(user_id)
    except Exception as e:
        logger.error("adaptive home feed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error building home feed layout",
        ) from e
