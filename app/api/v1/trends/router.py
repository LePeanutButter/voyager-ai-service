"""Predictive travel trends API (Feature 15)."""

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


@router.get("/dashboard", response_model=TrendsDashboardResponse)
async def trends_dashboard(service: TrendsServiceDep):
    try:
        await service.ensure_initialized()
        return service.get_dashboard()
    except Exception as e:
        logger.error("Trends dashboard failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build trends dashboard")


@router.get("/segments/{segment_id}/insights", response_model=SegmentInsightsResponse)
async def segment_insights(segment_id: str, service: TrendsServiceDep):
    try:
        await service.ensure_initialized()
        return service.get_segment_insights(segment_id)
    except Exception as e:
        logger.error("Segment insights failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate segment insights")


@router.get("/weekly-digest", response_model=WeeklyTrendsDigestResponse)
async def weekly_trends_digest(service: TrendsServiceDep):
    try:
        await service.ensure_initialized()
        return service.get_weekly_digest()
    except Exception as e:
        logger.error("Weekly digest failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build weekly digest")
