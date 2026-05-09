"""HTTP API for seasonality indices, forecasts, and visibility adjustments (business paper)."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SeasonalityServiceDep
from app.modules.seasonality.schemas import (
    SeasonalityIngestRequest,
    SeasonalForecastRequest,
    SeasonalForecastResponse,
    SeasonalityOverviewResponse,
    VisibilityAdjustmentsRequest,
    VisibilityAdjustmentsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/ingest/profiles",
    responses={500: {"description": "Failed to ingest seasonality profiles"}},
)
async def ingest_seasonality_profiles(body: SeasonalityIngestRequest, service: SeasonalityServiceDep):
    try:
        service.ingest_profiles([r.model_dump() for r in body.rows])
        return {"message": "Seasonality profiles ingested", "rows": len(body.rows)}
    except Exception as e:
        logger.error("seasonality ingest failed: %s", e)
        raise HTTPException(status_code=500, detail="Seasonality ingest failed") from e


@router.get(
    "/overview",
    response_model=SeasonalityOverviewResponse,
    summary="Perfiles estacionales (s=12) para destinos del catálogo",
    responses={500: {"description": "Seasonality overview failed"}},
)
async def seasonality_overview(
    service: SeasonalityServiceDep,
    reference_month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
):
    try:
        return service.overview(reference_month=reference_month)
    except Exception as e:
        logger.error("seasonality overview: %s", e)
        raise HTTPException(status_code=500, detail="Seasonality overview failed") from e


@router.get(
    "/destinations/{destination_id}",
    summary="Perfil estacional de un destino",
    responses={404: {"description": "Unknown destination_id for seasonality"}},
)
async def destination_seasonal_profile(destination_id: str, service: SeasonalityServiceDep):
    profile = service.profile(destination_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Unknown destination_id for seasonality")
    return profile


@router.post(
    "/forecast",
    response_model=SeasonalForecastResponse,
    summary="Pronóstico ingenuo estacional (placeholder hasta SARIMA con datos reales)",
    responses={500: {"description": "Forecast failed"}},
)
async def seasonal_forecast(body: SeasonalForecastRequest, service: SeasonalityServiceDep):
    try:
        return service.forecast_naive_seasonal(
            body.destination_id, body.start_month, body.horizon_months
        )
    except Exception as e:
        logger.error("seasonal forecast: %s", e)
        raise HTTPException(status_code=500, detail="Forecast failed") from e


@router.post(
    "/visibility-adjustments",
    response_model=VisibilityAdjustmentsResponse,
    summary="Factores de visibilidad por destino y mes (operadores / mitigación)",
    responses={500: {"description": "Visibility adjustments failed"}},
)
async def visibility_adjustments(body: VisibilityAdjustmentsRequest, service: SeasonalityServiceDep):
    try:
        return service.visibility_adjustments(
            body.destination_ids, body.travel_month, body.apply_mitigation
        )
    except Exception as e:
        logger.error("visibility adjustments: %s", e)
        raise HTTPException(status_code=500, detail="Visibility adjustments failed") from e
