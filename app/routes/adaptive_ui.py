"""
Feature 16 — UI adaptativa basada en comportamiento (PBI 32–33).

La adaptación del menú usa interacciones con `context.nav_item_id`.
El feed usa `activity_category` en POST /behavior-analysis/track.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.models.schemas import MenuAdaptationResponse, HomeFeedLayoutResponse
from app.services.adaptive_ui_service import AdaptiveUIService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_adaptive_ui_service(request: Request) -> AdaptiveUIService:
    svc = getattr(request.app.state, "adaptive_ui_service", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Adaptive UI service not initialised",
        )
    return svc


@router.get(
    "/menu/{user_id}",
    response_model=MenuAdaptationResponse,
    summary="Reorganización inteligente de menú (PBI 32)",
)
def get_adaptive_menu(
    user_id: str,
    service: Annotated[AdaptiveUIService, Depends(get_adaptive_ui_service)],
):
    """
    Devuelve entradas de navegación en `primary` y `secondary` según frecuencia
    de `context.nav_item_id` en la ventana configurada (30 días por defecto).
    """
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
def get_adaptive_home_feed(
    user_id: str,
    service: Annotated[AdaptiveUIService, Depends(get_adaptive_ui_service)],
):
    """
    Prioriza secciones y `recommendation_theme_weights` según intereses detectados
    (p. ej. aventura, cultura). Reutilizar esos pesos en
    `POST .../recommendations/destinations/personalized` vía `theme_weights`.
    """
    try:
        return service.build_home_feed_layout(user_id)
    except Exception as e:
        logger.error("adaptive home feed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error building home feed layout",
        ) from e
