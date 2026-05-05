"""HTTP endpoints for adaptive UI (menu and home feed).

Responsibilities:
    Expose GET routes parameterized by `user_id` delegating to `AdaptiveUIService`.

Dependencies:
    `app.api.deps.AdaptiveUIServiceDep`, schemas in `app.modules.adaptive_ui.schemas`.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdaptiveUIServiceDep
from app.modules.adaptive_ui.schemas import HomeFeedLayoutResponse, MenuAdaptationResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/menu/{user_id}",
    response_model=MenuAdaptationResponse,
    summary="Smart menu reordering (PBI 32)",
)
def get_adaptive_menu(user_id: str, service: AdaptiveUIServiceDep):
    """Builds menu adaptation for the given user.

    Args:
        user_id: Traveler identifier.
        service: Injected adaptive UI service.

    Returns:
        `MenuAdaptationResponse` with prioritized items.

    Raises:
        HTTPException: 500 if the service raises an unhandled error.
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
    summary="Dynamic home screen content (PBI 33)",
)
def get_adaptive_home_feed(user_id: str, service: AdaptiveUIServiceDep):
    """Builds the home feed layout for the user.

    Args:
        user_id: Traveler identifier.
        service: Injected adaptive UI service.

    Returns:
        `HomeFeedLayoutResponse` with feed sections.

    Raises:
        HTTPException: 500 if the service fails.
    """
    try:
        return service.build_home_feed_layout(user_id)
    except Exception as e:
        logger.error("adaptive home feed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error building home feed layout",
        ) from e
