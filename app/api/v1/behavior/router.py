"""HTTP router for user behavior tracking and analysis.

Responsibilities:
    Track interactions, run analysis, fetch summaries, batch tracking,
    and clear in-memory data when applicable.

Dependencies:
    `BehaviorAnalysisServiceDep`, schemas in `app.modules.behavior.schemas`,
    shared `APIResponse`.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from app.api.deps import BehaviorAnalysisServiceDep
from app.modules.behavior.schemas import (
    BehaviorAnalysisRequest,
    BehaviorTrackingRequest,
    ImplicitPreferenceUpdate,
)
from app.modules.common.schemas.base import APIResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/track", response_model=APIResponse)
async def track_user_behavior(
    body: BehaviorTrackingRequest,
    service: BehaviorAnalysisServiceDep,
):
    """Persists or enqueues a single behavior event.

    Args:
        body: Event payload (user, type, metadata).
        service: Behavior analysis service.

    Returns:
        `APIResponse` with `success` and confirmation data.

    Raises:
        HTTPException: 500 if tracking fails or on unexpected error.
    """
    try:
        success = await service.track_interaction(body)
        if success:
            return APIResponse(
                success=True,
                message="Behavior tracked successfully",
                data={"tracked": True},
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track behavior",
        )
    except Exception as e:
        logger.error("Error tracking behavior: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking behavior: {e}",
        )


@router.post("/analyze", response_model=ImplicitPreferenceUpdate)
async def analyze_user_behavior(
    body: BehaviorAnalysisRequest,
    service: BehaviorAnalysisServiceDep,
):
    """Runs aggregated analysis and returns implicit preference updates.

    Args:
        body: Time window and flags for patterns/updates.
        service: Analysis service.

    Returns:
        Result with detected patterns and preference hints.

    Raises:
        HTTPException: 400 on invalid parameters; 500 on internal error.
    """
    try:
        result = service.analyze_behavior(body)
        logger.info("Behavior analysis completed for user %s", body.user_id)
        return result
    except ValueError as e:
        logger.error("Invalid analysis request: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Error analyzing behavior: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing behavior: {e}",
        )


@router.get("/summary/{user_id}")
async def get_behavior_summary(
    user_id: str,
    service: BehaviorAnalysisServiceDep,
    days: int = 30,
):
    """Returns aggregated metrics for the user's recent activity.

    Args:
        user_id: User identifier.
        service: Analysis service.
        days: Lookback window in days.

    Returns:
        Summary dict per service implementation.

    Raises:
        HTTPException: 404 if the service embeds an error in the payload; 500 on failure.
    """
    try:
        summary = service.get_user_behavior_summary(user_id, days)
        if "error" in summary:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=summary["error"])
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting behavior summary: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting behavior summary: {e}",
        )


@router.post("/batch-track", response_model=APIResponse)
async def batch_track_behavior(
    batch_requests: List[BehaviorTrackingRequest],
    service: BehaviorAnalysisServiceDep,
):
    """Processes a list of behavior events sequentially.

    Args:
        batch_requests: Tracking requests collection.
        service: Analysis service.

    Returns:
        `APIResponse` with success and failure counts.

    Raises:
        HTTPException: 500 on unhandled batch error.
    """
    try:
        success_count = 0
        failed_count = 0
        for req in batch_requests:
            success = await service.track_interaction(req)
            if success:
                success_count += 1
            else:
                failed_count += 1
        return APIResponse(
            success=True,
            message=f"Batch tracking completed: {success_count} successful, {failed_count} failed",
            data={"successful": success_count, "failed": failed_count, "total": len(batch_requests)},
        )
    except Exception as e:
        logger.error("Error in batch tracking: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch tracking: {e}",
        )


@router.get("/patterns/{user_id}")
async def get_detected_patterns(
    user_id: str,
    service: BehaviorAnalysisServiceDep,
    days: int = 7,
):
    """Returns only detected patterns via `analyze_behavior` with constrained flags.

    Args:
        user_id: User to analyze.
        service: Analysis service.
        days: Window in days.

    Returns:
        Dict with period, serialized pattern list, and confidence.

    Raises:
        HTTPException: 400 or 500 depending on validation and internal errors.
    """
    try:
        req = BehaviorAnalysisRequest(
            user_id=user_id,
            analysis_period_days=days,
            include_patterns=True,
            include_preference_updates=False,
        )
        result = service.analyze_behavior(req)
        return {
            "user_id": user_id,
            "analysis_period": result.analysis_period.model_dump(),
            "patterns": [pattern.model_dump() for pattern in result.detected_patterns],
            "confidence_score": result.confidence_score,
        }
    except ValueError as e:
        logger.error("Invalid pattern request: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Error getting patterns: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting patterns: {e}",
        )


@router.delete("/clear/{user_id}", response_model=APIResponse)
async def clear_user_behavior_data(user_id: str, service: BehaviorAnalysisServiceDep):
    """Clears in-memory behavior data for the user if present.

    Args:
        user_id: User whose data is purged.
        service: Service instance (may expose `behavior_data`).

    Returns:
        `APIResponse` indicating whether rows were deleted.

    Raises:
        HTTPException: 500 on unexpected error.
    """
    try:
        if hasattr(service, "behavior_data") and user_id in service.behavior_data:
            del service.behavior_data[user_id]
            return APIResponse(
                success=True,
                message="Behavior data cleared successfully",
                data={"cleared": True},
            )
        return APIResponse(
            success=True,
            message="No behavior data found to clear",
            data={"cleared": False},
        )
    except Exception as e:
        logger.error("Error clearing behavior data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing behavior data: {e}",
        )
