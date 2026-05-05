"""
Predictive travel trends (Feature 15).

PBI 30: emerging destinations from aggregated search-style signals (30-day windows).
PBI 31: segment behavior insights and weekly micro-trend + partner notifications (API payload;
        real weekly jobs + outbound notifications belong in infrastructure).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.core.config import settings
from app.modules.trends.schemas import (
    EmergingDestinationTrend,
    MicroTrendOpportunity,
    PartnerTrendNotification,
    SeasonalPattern,
    SegmentBehaviorInsight,
    SegmentInsightsResponse,
    TrendsDashboardResponse,
    WeeklyTrendsDigestResponse,
)

logger = logging.getLogger(__name__)

# Synthetic aggregated “search” volumes: current vs previous 30-day windows.
# Surge ratio = (current - previous) / previous (PBI 30: mark emerging when >= 50%).
_SIGNAL_SEED: List[Dict[str, Any]] = [
    {
        "destination_id": "dst_azores",
        "name": "Azores",
        "country": "Portugal",
        "tags": ["nature", "adventure", "relaxation"],
        "previous": 4200,
        "current": 7800,
    },
    {
        "destination_id": "dst_georgia",
        "name": "Georgia (Caucasus)",
        "country": "Georgia",
        "tags": ["cultural", "foodie", "adventure"],
        "previous": 3100,
        "current": 6200,
    },
    {
        "destination_id": "dst_slovenia",
        "name": "Slovenia",
        "country": "Slovenia",
        "tags": ["nature", "cultural", "foodie"],
        "previous": 5100,
        "current": 6900,
    },
    {
        "destination_id": "dst_lisbon",
        "name": "Lisbon",
        "country": "Portugal",
        "tags": ["cultural", "foodie", "beach"],
        "previous": 88000,
        "current": 90000,
    },
]

_SEGMENT_LIBRARY: Dict[str, Dict[str, Any]] = {
    "family_budget": {
        "label": "Familias presupuesto medio",
        "seasonal": [
            {"label": "Picos escolares (Jul–Aug)", "intensity": 0.82, "months_peak": [7, 8]},
            {"label": "Semana santa / puentes", "intensity": 0.64, "months_peak": [3, 4, 12]},
        ],
        "budget": {"median_daily_usd": 120, "elasticity": "high"},
        "preferences": ["beach", "cultural", "relaxation"],
    },
    "solo_luxury": {
        "label": "Solo traveler premium",
        "seasonal": [
            {"label": "Shoulder season premium", "intensity": 0.71, "months_peak": [5, 6, 9, 10]},
        ],
        "budget": {"median_daily_usd": 380, "elasticity": "low"},
        "preferences": ["foodie", "cultural", "nature"],
    },
    "eco_conscious": {
        "label": "Turismo consciente / slow travel",
        "seasonal": [
            {"label": "Primavera / otoño outdoor", "intensity": 0.77, "months_peak": [4, 5, 9, 10]},
        ],
        "budget": {"median_daily_usd": 160, "elasticity": "medium"},
        "preferences": ["nature", "adventure", "cultural"],
    },
}


class TrendsService:
    """In-memory trend engine; replace with warehouse + batch ML in production."""

    def __init__(self) -> None:
        self._last_refresh: Optional[datetime] = None
        self._emerging: List[EmergingDestinationTrend] = []

    async def ensure_initialized(self) -> None:
        if not self._emerging:
            await self.refresh()

    async def refresh(self) -> None:
        """Recompute emerging flags from the last configured window (mock ingest)."""
        window = settings.TREND_ANALYSIS_WINDOW_DAYS
        threshold = settings.TREND_EMERGENCE_SURGE_RATIO
        emerging: List[EmergingDestinationTrend] = []

        for row in _SIGNAL_SEED:
            prev_v = int(row["previous"])
            cur_v = int(row["current"])
            if prev_v <= 0:
                surge = 1.0 if cur_v > 0 else 0.0
            else:
                surge = (cur_v - prev_v) / prev_v
            is_emerging = surge >= threshold
            label = "Tendencia emergente" if is_emerging else "Estable / maduro"

            emerging.append(
                EmergingDestinationTrend(
                    destination_id=row["destination_id"],
                    name=row["name"],
                    country=row["country"],
                    tags=list(row.get("tags", [])),
                    search_volume_previous_window=prev_v,
                    search_volume_current_window=cur_v,
                    surge_ratio=round(float(surge), 4),
                    analyzed_window_days=window,
                    is_emerging=is_emerging,
                    dashboard_label=label,
                )
            )

        self._emerging = emerging
        self._last_refresh = datetime.now(timezone.utc)
        logger.info("Trends refreshed: %s emerging of %s", sum(1 for e in emerging if e.is_emerging), len(emerging))

    def get_dashboard(self) -> TrendsDashboardResponse:
        if not self._emerging:
            raise RuntimeError("TrendsService not initialised; call ensure_initialized() or refresh()")
        emerging_only = [e for e in self._emerging if e.is_emerging]
        summary = (
            f"Ventana {settings.TREND_ANALYSIS_WINDOW_DAYS}d: "
            f"{len(emerging_only)} destinos superan crecimiento ≥{settings.TREND_EMERGENCE_SURGE_RATIO:.0%} vs ventana previa."
        )
        return TrendsDashboardResponse(
            generated_at=datetime.now(timezone.utc),
            window_days=settings.TREND_ANALYSIS_WINDOW_DAYS,
            emerging_destinations=emerging_only,
            summary=summary,
        )

    def get_full_signals(self) -> List[EmergingDestinationTrend]:
        return list(self._emerging)

    def emerging_for_preferences(self, pref_values: Set[str]) -> List[Dict[str, Any]]:
        """
        Destinations currently emerging and compatible with user tag preferences (PBI 30 AC2).
        """
        out: List[Dict[str, Any]] = []
        for t in self._emerging:
            if not t.is_emerging:
                continue
            if pref_values & set(t.tags):
                out.append(
                    {
                        "destination_id": t.destination_id,
                        "name": t.name,
                        "country": t.country,
                        "tags": t.tags,
                        "surge_ratio": t.surge_ratio,
                    }
                )
        return sorted(out, key=lambda x: x["surge_ratio"], reverse=True)

    def get_segment_insights(self, segment_id: str) -> SegmentInsightsResponse:
        """PBI 31: predictive-style snapshot for a traveler segment."""
        data = _SEGMENT_LIBRARY.get(segment_id)
        if not data:
            data = _SEGMENT_LIBRARY["family_budget"]
            segment_id = "family_budget"

        seasonal = [
            SeasonalPattern(
                label=s["label"],
                intensity=float(s["intensity"]),
                months_peak=list(s.get("months_peak", [])),
            )
            for s in data["seasonal"]
        ]

        insight = SegmentBehaviorInsight(
            segment_id=segment_id,
            segment_label=str(data["label"]),
            seasonal_patterns=seasonal,
            budget_profile=dict(data["budget"]),
            top_preferences=list(data["preferences"]),
            confidence=0.78,
        )
        return SegmentInsightsResponse(generated_at=datetime.now(timezone.utc), insights=insight)

    def get_weekly_digest(self) -> WeeklyTrendsDigestResponse:
        """PBI 31: micro-tendencias + avisos para empresas (payload semanal simulado)."""
        iso = datetime.now(timezone.utc).isocalendar()
        week_label = f"{iso.year}-W{iso.week:02d}"

        micro = [
            MicroTrendOpportunity(
                trend_id="mt_slow_train_europe",
                title="Micro-tendencia: viajes en tren nocturno < 6h",
                affected_segments=["eco_conscious", "solo_luxury"],
                opportunity_score=0.86,
                suggested_action="Empaquetar rutas multi-ciudad con carbono explícito bajo.",
            ),
            MicroTrendOpportunity(
                trend_id="mt_local_cuisine_workshop",
                title="Talleres culinarios hiperlocales (+35% intención vs trimestre anterior)",
                affected_segments=["family_budget", "solo_luxury"],
                opportunity_score=0.74,
                suggested_action="Cruzar datos de destinos emergentes con chefs partners.",
            ),
        ]

        notifications = [
            PartnerTrendNotification(
                notification_id=f"pn_{week_label}_1",
                target_partner_profile="Tour operadores premium Europa",
                micro_trend_id=micro[0].trend_id,
                message=(
                    "Nueva micro-tren nocturno: audiencias eco + solo luxury muestran elasticidad de precio "
                    "positiva para bundles 4–5 noches."
                ),
                weekly_cycle_anchor=week_label,
            ),
            PartnerTrendNotification(
                notification_id=f"pn_{week_label}_2",
                target_partner_profile="DMO / destinos emergentes",
                micro_trend_id=micro[1].trend_id,
                message=(
                    "Oportunidad de co-marketing con talleres locales en destinos con surge ≥50% "
                    "(ver dashboard de tendencias)."
                ),
                weekly_cycle_anchor=week_label,
            ),
        ]

        return WeeklyTrendsDigestResponse(
            generated_at=datetime.now(timezone.utc),
            micro_trends=micro,
            partner_notifications=notifications,
        )
