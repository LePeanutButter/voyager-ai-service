"""
Predictive travel trends API (Feature 15).

PBI 30: emerging destinations dashboard + linkage to personalized recommendations.
PBI 31: segment insights and weekly digest with partner notifications payload.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import (
    TrendsDashboardResponse,
    SegmentInsightsResponse,
    WeeklyTrendsDigestResponse,
)
from app.services.trends_service import TrendsService

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_trends_service(request: Request) -> TrendsService:
    service = getattr(request.app.state, "trends_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Trends service not available")
    return service


@router.get("/dashboard", response_model=TrendsDashboardResponse)
async def trends_dashboard(service: TrendsService = Depends(get_trends_service)):
    """
    PBI 30: destinos emergentes (crecimiento ≥ umbral vs ventana previa de 30 días).
    """
    try:
        await service.ensure_initialized()
        return service.get_dashboard()
    except Exception as e:
        logger.error("Trends dashboard failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build trends dashboard")


@router.get("/segments/{segment_id}/insights", response_model=SegmentInsightsResponse)
async def segment_insights(
    segment_id: str,
    service: TrendsService = Depends(get_trends_service),
):
    """
    PBI 31: patrones de temporada, presupuesto y preferencias por segmento de viajeros.
    """
    try:
        await service.ensure_initialized()
        return service.get_segment_insights(segment_id)
    except Exception as e:
        logger.error("Segment insights failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate segment insights")


@router.get("/weekly-digest", response_model=WeeklyTrendsDigestResponse)
async def weekly_trends_digest(service: TrendsService = Depends(get_trends_service)):
    """
    PBI 31: micro-tendencias y notificaciones sugeridas para empresas (ciclo semanal simulado).
    En producción: sustituir por job semanal + cola de notificaciones reales.
    """
    try:
        await service.ensure_initialized()
        return service.get_weekly_digest()
    except Exception as e:
        logger.error("Weekly digest failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build weekly digest")
