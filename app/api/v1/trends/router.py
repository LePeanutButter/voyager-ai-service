"""Predictive travel trends API (dashboard, segments, digest).

Responsibilities:
    Serve aggregated views from `TrendsService` after ensuring initialization.

Dependencies:
    `TrendsServiceDep`, schemas in `app.modules.trends.schemas`.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import TrendsServiceDep
from app.modules.trends.schemas import (
    SegmentInsightsResponse,
    TrendsDashboardResponse,
    WeeklyTrendsDigestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/dashboard",
    response_model=TrendsDashboardResponse,
    responses={500: {"description": "Failed to build trends dashboard"}},
)
async def trends_dashboard(service: TrendsServiceDep):
    """Returns the trends dashboard (emerging destinations, signals, etc.).

    Args:
        service: Injected trends service.

    Returns:
        Serializable `TrendsDashboardResponse`.

    Raises:
        HTTPException: 500 if the dashboard cannot be built.
    """
    try:
        await service.ensure_initialized()
        return service.get_dashboard()
    except Exception as e:
        logger.error("Trends dashboard failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build trends dashboard")


@router.get(
    "/segments/{segment_id}/insights",
    response_model=SegmentInsightsResponse,
    responses={500: {"description": "Failed to generate segment insights"}},
)
async def segment_insights(segment_id: str, service: TrendsServiceDep):
    """Returns the predictive snapshot for a traveler segment.

    Args:
        segment_id: Segment key (internal catalog or fallback).
        service: Trends service.

    Returns:
        `SegmentInsightsResponse` with patterns and budget profile.

    Raises:
        HTTPException: 500 if generation fails.
    """
    try:
        await service.ensure_initialized()
        return service.get_segment_insights(segment_id)
    except Exception as e:
        logger.error("Segment insights failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate segment insights")


@router.get(
    "/weekly-digest",
    response_model=WeeklyTrendsDigestResponse,
    responses={500: {"description": "Failed to build weekly digest"}},
)
async def weekly_trends_digest(service: TrendsServiceDep):
    """Returns the weekly digest of micro-trends and partner notices.

    Args:
        service: Trends service.

    Returns:
        `WeeklyTrendsDigestResponse`.

    Raises:
        HTTPException: 500 if the digest cannot be built.
    """
    try:
        await service.ensure_initialized()
        return service.get_weekly_digest()
    except Exception as e:
        logger.error("Weekly digest failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build weekly digest")
