"""Seasonality engine aligned with digital-transformation.tex (mitigación / SARIMA / PEAS).

The paper models seasonality with SARIMA (seasonal period s) and proposes dynamic
destination visibility to mitigate peaks and valleys. This module uses a lightweight
monthly demand simulation (period s=12), seasonal indices by calendar month, and
visibility multipliers for ranking — suitable without a full statsmodels fit until
real time series are ingested from RDS / analytics.
"""

from __future__ import annotations

import math
import json
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Tuple

from sqlalchemy import select

from app.core.config import settings
from app.db import database as db_database
from app.db.runtime_models import SeasonalityProfileRecord
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

_KNOWN_DESTINATIONS: List[Tuple[str, str, str, bool]] = []

Phase = Literal["peak", "shoulder", "off_peak"]


class SeasonalityService:
    """Monthly seasonal indices (s=12) and visibility mitigation for recommendations."""

    def __init__(self) -> None:
        db_database.init_db_engine()
        self._monthly_index: Dict[str, List[float]] = {}
        self._destination_meta: Dict[str, Tuple[str, str]] = {}
        self._load_profiles()

    @staticmethod
    def _db():
        assert db_database.SessionLocal is not None
        return db_database.SessionLocal()

    def _load_profiles(self) -> None:
        with self._db() as db:
            rows = db.scalars(select(SeasonalityProfileRecord)).all()
        for row in rows:
            self._monthly_index[row.destination_id] = [float(x) for x in json.loads(row.monthly_indices_json)]
            self._destination_meta[row.destination_id] = (row.name, row.country)

    def ingest_profiles(self, rows: List[Dict[str, object]]) -> None:
        """Replace in-memory seasonal profiles with external ingested data."""
        self._monthly_index = {}
        self._destination_meta = {}
        persist_rows: List[SeasonalityProfileRecord] = []
        for row in rows:
            destination_id = str(row["destination_id"])
            indices = [float(x) for x in row["monthly_indices"]]
            if len(indices) != 12:
                raise ValueError("monthly_indices must contain exactly 12 values")
            self._monthly_index[destination_id] = indices
            self._destination_meta[destination_id] = (str(row["name"]), str(row["country"]))
            persist_rows.append(
                SeasonalityProfileRecord(
                    destination_id=destination_id,
                    name=str(row["name"]),
                    country=str(row["country"]),
                    monthly_indices_json=json.dumps(indices),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        with self._db() as db:
            for old in db.scalars(select(SeasonalityProfileRecord)).all():
                db.delete(old)
            for pr in persist_rows:
                db.add(pr)
            db.commit()

    def demand_index(self, destination_id: str, month: int) -> float:
        """Relative demand vs annual mean for calendar month (1–12)."""
        m = max(1, min(12, month))
        row = self._monthly_index.get(destination_id)
        if not row:
            raise ValueError(f"destination_id '{destination_id}' not ingested")
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
        meta = self._destination_meta.get(destination_id, (destination_id, ""))
        name = meta[0]
        country = meta[1]
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
        for dest_id in self._monthly_index.keys():
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
                methodology_note="Destino sin serie cargada; ingiere perfiles estacionales vía endpoint.",
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
