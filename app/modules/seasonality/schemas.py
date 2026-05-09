"""Schemas for seasonality-aware demand and visibility (paper: SARIMA / mitigación)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SeasonalContext(BaseModel):
    """Context attached to a destination card when mitigation is applied."""

    reference_month: int = Field(..., ge=1, le=12, description="Mes de viaje usado para el índice.")
    demand_index: float = Field(
        ...,
        ge=0.0,
        description="Índice relativo a la media anual (1.0 = neutral). Analogía demanda estacional.",
    )
    phase: Literal["peak", "shoulder", "off_peak"] = "shoulder"
    visibility_multiplier: float = Field(
        ...,
        ge=0.5,
        le=1.5,
        description="Factor aplicado al score para mitigar estacionalidad (PEAS: visibilidad dinámica).",
    )


class MonthlyDemandPoint(BaseModel):
    month: int = Field(..., ge=1, le=12)
    index: float = Field(..., description="Promedio histórico del mes / media global (~1).")
    phase: Literal["peak", "shoulder", "off_peak"]


class DestinationSeasonalProfile(BaseModel):
    destination_id: str
    name: str
    country: str
    seasonal_period_months: int = Field(12, description="s=12 (componente estacional tipo SARIMA).")
    monthly_indices: List[MonthlyDemandPoint]
    series_variability: float = Field(
        0.0,
        description="Coef. variación de índices mensuales; proxy de fuerza estacional.",
    )


class SeasonalityOverviewResponse(BaseModel):
    generated_at: datetime
    reference_month: int
    destinations: List[DestinationSeasonalProfile]
    methodology_note: str


class SeasonalForecastRequest(BaseModel):
    destination_id: str
    start_month: int = Field(..., ge=1, le=12, description="Mes calendario inicial (1–12).")
    horizon_months: int = Field(6, ge=1, le=24)


class ForecastPoint(BaseModel):
    month: int = Field(..., ge=1, le=12)
    forecast_index: float
    method: str = "seasonal_naive"


class SeasonalForecastResponse(BaseModel):
    destination_id: str
    generated_at: datetime
    points: List[ForecastPoint]
    methodology_note: str


class VisibilityAdjustmentsRequest(BaseModel):
    """Cuerpo para operadores: factores de visibilidad por destino y mes."""

    destination_ids: List[str]
    travel_month: int = Field(..., ge=1, le=12)
    apply_mitigation: bool = True


class VisibilityAdjustmentRow(BaseModel):
    destination_id: str
    demand_index: float
    phase: Literal["peak", "shoulder", "off_peak"]
    visibility_multiplier: float
    recommendation: str


class VisibilityAdjustmentsResponse(BaseModel):
    travel_month: int
    rows: List[VisibilityAdjustmentRow]
    methodology_note: str


class SeasonalityIngestRow(BaseModel):
    destination_id: str
    name: str
    country: str
    monthly_indices: List[float] = Field(min_length=12, max_length=12)


class SeasonalityIngestRequest(BaseModel):
    rows: List[SeasonalityIngestRow] = Field(min_length=1)
