"""Seasonality engine aligned with digital-transformation.tex (mitigación / SARIMA / PEAS).

The paper models seasonality with SARIMA (seasonal period s) and proposes dynamic
destination visibility to mitigate peaks and valleys. This module uses a lightweight
monthly demand simulation (period s=12), seasonal indices by calendar month, and
visibility multipliers for ranking — suitable without a full statsmodels fit until
real time series are ingested from RDS / analytics.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Tuple

from app.core.config import settings
from app.modules.seasonality.schemas import (
    DestinationSeasonalProfile,
    ForecastPoint,
    MonthlyDemandPoint,
    SeasonalForecastResponse,
    SeasonalityOverviewResponse,
    SeasonalContext,
    VisibilityAdjustmentRow,
    VisibilityAdjustmentsResponse,
)

# Mirrors destination catalog IDs (avoid import cycle with recommendations.service).
_KNOWN_DESTINATIONS: List[Tuple[str, str, str, bool]] = [
    ("dst_barcelona", "Barcelona", "Spain", False),
    ("dst_kyoto", "Kyoto", "Japan", False),
    ("dst_queenstown", "Queenstown", "New Zealand", True),
    ("dst_maldives", "Maldives", "Maldives", False),
    ("dst_lima", "Lima", "Peru", False),
    ("dst_reykjavik", "Reykjavik", "Iceland", False),
    ("dst_marrakech", "Marrakech", "Morocco", False),
    ("dst_bali", "Bali", "Indonesia", False),
    ("dst_lisbon", "Lisbon", "Portugal", False),
    ("dst_patagonia", "Patagonia", "Argentina/Chile", True),
    ("dst_azores", "Azores", "Portugal", False),
    ("dst_georgia", "Georgia (Caucasus)", "Georgia", False),
    ("dst_slovenia", "Slovenia", "Slovenia", False),
]

Phase = Literal["peak", "shoulder", "off_peak"]


class SeasonalityService:
    """Monthly seasonal indices (s=12) and visibility mitigation for recommendations."""

    def __init__(self) -> None:
        self._monthly_index: Dict[str, List[float]] = {}
        self._build_profiles()

    def _synthetic_monthly_demands(
        self, destination_id: str, southern_hemisphere: bool
    ) -> List[float]:
        """36 months of synthetic demand (seasonal + noise); base for seasonal averages."""
        rng = random.Random(hash(destination_id) % (2**31))
        series: List[float] = []
        for t in range(settings.SEASONALITY_HISTORY_MONTHS):
            month = (t % 12) + 1
            # Peak in northern summer by default; invert phase for southern ski/summer
            angle = 2.0 * math.pi * (month - 6.5) / 12.0
            if southern_hemisphere:
                angle = -angle
            seasonal = 1.0 + settings.SEASONALITY_AMPLITUDE * math.sin(angle)
            noise = rng.uniform(0.94, 1.06)
            series.append(max(0.05, seasonal * noise))
        return series

    def _build_profiles(self) -> None:
        for dest_id, _name, _country, south in _KNOWN_DESTINATIONS:
            series = self._synthetic_monthly_demands(dest_id, south)
            buckets: List[List[float]] = [[] for _ in range(12)]
            for t, v in enumerate(series):
                m = (t % 12)
                buckets[m].append(v)
            monthly_avg = [sum(b) / len(b) for b in buckets]
            overall = sum(monthly_avg) / 12.0
            indices = [round(x / overall, 4) for x in monthly_avg]
            self._monthly_index[dest_id] = indices

    def demand_index(self, destination_id: str, month: int) -> float:
        """Relative demand vs annual mean for calendar month (1–12)."""
        m = max(1, min(12, month))
        row = self._monthly_index.get(destination_id)
        if not row:
            return 1.0
        return float(row[m - 1])

    def classify_phase(self, index: float) -> Phase:
        peak = settings.SEASONALITY_PEAK_THRESHOLD
        low = settings.SEASONALITY_OFFPEAK_THRESHOLD
        if index >= peak:
            return "peak"
        if index <= low:
            return "off_peak"
        return "shoulder"

    def visibility_multiplier(self, destination_id: str, month: int) -> Tuple[float, Phase, float]:
        """Returns (demand_index, phase, multiplier) for ranking mitigation."""
        idx = self.demand_index(destination_id, month)
        phase = self.classify_phase(idx)
        k = settings.SEASONALITY_MITIGATION_STRENGTH
        if idx <= 1.0:
            mult = 1.0 + k * (1.0 - idx)
        else:
            mult = 1.0 - k * min(idx - 1.0, settings.SEASONALITY_PEAK_DAMP_CAP)
        mult = max(settings.SEASONALITY_MULT_MIN, min(settings.SEASONALITY_MULT_MAX, mult))
        return idx, phase, mult

    def seasonal_context(self, destination_id: str, month: int) -> SeasonalContext:
        idx, phase, mult = self.visibility_multiplier(destination_id, month)
        return SeasonalContext(
            reference_month=month,
            demand_index=round(idx, 4),
            phase=phase,
            visibility_multiplier=round(mult, 4),
        )

    def profile(self, destination_id: str) -> Optional[DestinationSeasonalProfile]:
        row = self._monthly_index.get(destination_id)
        if not row:
            return None
        meta = next((x for x in _KNOWN_DESTINATIONS if x[0] == destination_id), None)
        name = meta[1] if meta else destination_id
        country = meta[2] if meta else ""
        points: List[MonthlyDemandPoint] = []
        for mi, idx in enumerate(row, start=1):
            points.append(
                MonthlyDemandPoint(month=mi, index=idx, phase=self.classify_phase(idx))
            )
        variability = _coefficient_of_variation(row)
        return DestinationSeasonalProfile(
            destination_id=destination_id,
            name=name,
            country=country,
            monthly_indices=points,
            series_variability=round(variability, 4),
        )

    def overview(self, reference_month: Optional[int] = None) -> SeasonalityOverviewResponse:
        now_m = reference_month or datetime.now(timezone.utc).month
        profiles: List[DestinationSeasonalProfile] = []
        for dest_id, _, _, _ in _KNOWN_DESTINATIONS:
            p = self.profile(dest_id)
            if p:
                profiles.append(p)
        note = (
            "Índices mensuales con periodo estacional s=12 (análogo al componente estacional SARIMA del paper); "
            "multiplicadores de visibilidad mitigan picos y refuerzan meses valle (PEAS — actuadores)."
        )
        return SeasonalityOverviewResponse(
            generated_at=datetime.now(timezone.utc),
            reference_month=now_m,
            destinations=profiles,
            methodology_note=note,
        )

    def forecast_naive_seasonal(
        self, destination_id: str, start_month: int, horizon_months: int
    ) -> SeasonalForecastResponse:
        """Seasonal naive forecast: each future month uses historical seasonal index."""
        row = self._monthly_index.get(destination_id)
        if not row:
            return SeasonalForecastResponse(
                destination_id=destination_id,
                generated_at=datetime.now(timezone.utc),
                points=[],
                methodology_note="Destino sin serie sintética; ingesta RDS pendiente.",
            )
        points: List[ForecastPoint] = []
        m = max(1, min(12, start_month))
        for h in range(1, horizon_months + 1):
            # Primer paso = mes calendario siguiente al ancla (h=1 → mes siguiente a start_month).
            cal = ((m - 1 + h) % 12) + 1
            points.append(
                ForecastPoint(
                    month=cal,
                    forecast_index=float(row[cal - 1]),
                    method="seasonal_naive",
                )
            )
        note = (
            "Pronóstico ingenuo estacional: ŷ reutiliza el índice medio del mismo mes calendario; "
            "con datos reales conviene SARIMA/SARIMAX (Box-Jenkins) como en el marco teórico."
        )
        return SeasonalForecastResponse(
            destination_id=destination_id,
            generated_at=datetime.now(timezone.utc),
            points=points,
            methodology_note=note,
        )

    def visibility_adjustments(
        self, destination_ids: List[str], travel_month: int, apply_mitigation: bool
    ) -> VisibilityAdjustmentsResponse:
        rows: List[VisibilityAdjustmentRow] = []
        m = max(1, min(12, travel_month))
        for did in destination_ids:
            idx = self.demand_index(did, m)
            phase = self.classify_phase(idx)
            if apply_mitigation:
                _, _, mult = self.visibility_multiplier(did, m)
            else:
                mult = 1.0
            if phase == "peak":
                rec = "Moderar promoción; sugerir alternativas hombro/baja si aplica política de capacidad."
            elif phase == "off_peak":
                rec = "Aumentar visibilidad y bundles; alinea mitigación de estacionalidad (paper)."
            else:
                rec = "Mantener visibilidad equilibrada."
            rows.append(
                VisibilityAdjustmentRow(
                    destination_id=did,
                    demand_index=round(idx, 4),
                    phase=phase,
                    visibility_multiplier=round(mult, 4),
                    recommendation=rec,
                )
            )
        return VisibilityAdjustmentsResponse(
            travel_month=m,
            rows=rows,
            methodology_note="Factores para ajuste dinámico de visibilidad de destinos (KPI: variabilidad estacional).",
        )


def _coefficient_of_variation(values: List[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean <= 1e-9:
        return 0.0
    var = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(var) / mean
