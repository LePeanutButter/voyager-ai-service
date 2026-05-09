"""Predictive travel trends engine (Feature 15).

Purpose:
    Simulate aggregated search-like signal ingest and expose emerging destinations,
    segment insights, and a weekly partner digest.

Responsibilities:
    Refresh in-memory metrics (PBI 30), build segment and micro-trend payloads (PBI 31);
    real jobs and outbound notifications stay out of scope.

Dependencies:
    ``settings`` for thresholds and windows, schemas in ``app.modules.trends.schemas``.
"""

from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select

from app.core.config import settings
from app.db import database as db_database
from app.db.runtime_models import TrendSegmentRecord, TrendSignalRecord
from app.modules.trends.schemas import (
    EmergingDestinationTrend,
    MicroTrendGeo,
    MicroTrendOpportunity,
    PartnerTrendNotification,
    SeasonalPattern,
    SegmentBehaviorInsight,
    SegmentInsightsResponse,
    TrendsDashboardResponse,
    WeeklyTrendsDigestResponse,
)

logger = logging.getLogger(__name__)

_SIGNAL_SEED: List[Dict[str, Any]] = []
_SEGMENT_LIBRARY: Dict[str, Dict[str, Any]] = {}


class TrendsService:
    """In-memory trends engine; replace with warehouse and batch ML in production.

    Important attributes:
        _last_refresh: Timestamp of last successful ``refresh``.
        _emerging: Materialized list of ``EmergingDestinationTrend``.
    """

    def __init__(self) -> None:
        db_database.init_db_engine()
        self._last_refresh: Optional[datetime] = None
        self._emerging: List[EmergingDestinationTrend] = []
        self._signal_rows: List[Dict[str, Any]] = []
        self._segment_library: Dict[str, Dict[str, Any]] = {}
        self._load_ingested_state()

    @staticmethod
    def _db():
        assert db_database.SessionLocal is not None
        return db_database.SessionLocal()

    def _load_ingested_state(self) -> None:
        with self._db() as db:
            signal_rows = db.scalars(select(TrendSignalRecord)).all()
            segment_rows = db.scalars(select(TrendSegmentRecord)).all()
        self._signal_rows = [
            {
                "destination_id": r.destination_id,
                "name": r.name,
                "country": r.country,
                "tags": json.loads(r.tags_json or "[]"),
                "previous": r.previous,
                "current": r.current,
            }
            for r in signal_rows
        ]
        self._segment_library = {
            r.segment_id: json.loads(r.payload_json or "{}")
            for r in segment_rows
        }

    def ingest_signal_rows(self, rows: List[Dict[str, Any]]) -> None:
        """Upsert/replace trend signal rows from external data ingestion."""
        self._signal_rows = [dict(r) for r in rows]
        with self._db() as db:
            for old in db.scalars(select(TrendSignalRecord)).all():
                db.delete(old)
            for row in self._signal_rows:
                db.add(
                    TrendSignalRecord(
                        destination_id=row["destination_id"],
                        name=row["name"],
                        country=row["country"],
                        tags_json=json.dumps(row.get("tags", [])),
                        previous=int(row["previous"]),
                        current=int(row["current"]),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()
        logger.info("Trends ingested rows: %s", len(self._signal_rows))

    def ingest_segment_library(self, library: Dict[str, Dict[str, Any]]) -> None:
        """Upsert/replace segment insights source from external ingestion."""
        self._segment_library = dict(library)
        with self._db() as db:
            for old in db.scalars(select(TrendSegmentRecord)).all():
                db.delete(old)
            for sid, payload in self._segment_library.items():
                db.add(
                    TrendSegmentRecord(
                        segment_id=sid,
                        payload_json=json.dumps(payload),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            db.commit()
        logger.info("Trends ingested segment profiles: %s", len(self._segment_library))

    async def ensure_initialized(self) -> None:
        """Ensures materialized data by calling ``refresh`` if the list is empty."""
        if not self._signal_rows:
            raise RuntimeError("No trends signal rows ingested. POST /api/v1/trends/ingest/signals first.")
        if not self._emerging:
            await self.refresh()

    async def refresh(self) -> None:
        """Recomputes emerging flags from ingested signal rows and configuration thresholds."""
        await asyncio.sleep(0)
        window = settings.TREND_ANALYSIS_WINDOW_DAYS
        threshold = settings.TREND_EMERGENCE_SURGE_RATIO
        emerging: List[EmergingDestinationTrend] = []

        for row in self._signal_rows:
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
        """Returns the dashboard with only emerging-flagged destinations and summary.

        Returns:
            ``TrendsDashboardResponse`` with window and filtered list.

        Raises:
            RuntimeError: If ``ensure_initialized`` or ``refresh`` was not called first.
        """
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
        """Exposes all trend rows without filtering by ``is_emerging``.

        Returns:
            Shallow copy of the internal list.
        """
        return list(self._emerging)

    def emerging_for_preferences(self, pref_values: Set[str]) -> List[Dict[str, Any]]:
        """Lists emerging destinations whose tags intersect user preferences.

        Args:
            pref_values: Set of preference tags (e.g. ``cultural``).

        Returns:
            Dicts sorted by ``surge_ratio`` descending.
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
        """Returns a predictive-style snapshot for a traveler segment (PBI 31).

        Args:
            segment_id: Key in the internal library; falls back to ``family_budget``.

        Returns:
            Response with seasonal patterns and budget profile from ingested segment data.
        """
        data = self._segment_library.get(segment_id)
        if not data:
            raise RuntimeError(
                f"Segment '{segment_id}' not found. Ingest segment library before requesting insights."
            )

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
        """Builds weekly digest with micro-trends and business notices (simulated, PBI 31).

        Returns:
            Payload with opportunities and notifications anchored to the current ISO week.
        """
        iso = datetime.now(timezone.utc).isocalendar()
        week_label = f"{iso.year}-W{iso.week:02d}"

        micro = [
            MicroTrendOpportunity(
                trend_id="mt_slow_train_europe",
                title="Micro-tendencia: viajes en tren nocturno < 6h",
                affected_segments=["eco_conscious", "solo_luxury"],
                opportunity_score=0.86,
                suggested_action="Empaquetar rutas multi-ciudad con carbono explícito bajo.",
                geo=MicroTrendGeo(
                    destination_id="dst_zurich",
                    name="Zurich",
                    country="Switzerland",
                    latitude=47.3769,
                    longitude=8.5417,
                    city_code="ZRH",
                ),
            ),
            MicroTrendOpportunity(
                trend_id="mt_local_cuisine_workshop",
                title="Talleres culinarios hiperlocales (+35% intención vs trimestre anterior)",
                affected_segments=["family_budget", "solo_luxury"],
                opportunity_score=0.74,
                suggested_action="Cruzar datos de destinos emergentes con chefs partners.",
                geo=MicroTrendGeo(
                    destination_id="dst_oaxaca",
                    name="Oaxaca",
                    country="Mexico",
                    latitude=17.0732,
                    longitude=-96.7266,
                    city_code="OAX",
                ),
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
