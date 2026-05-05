from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class EmergingDestinationTrend(BaseModel):
    destination_id: str
    name: str
    country: str
    tags: List[str] = Field(default_factory=list)
    search_volume_previous_window: int = 0
    search_volume_current_window: int = 0
    surge_ratio: float = Field(..., description="(current - previous) / previous when previous > 0")
    analyzed_window_days: int = 30
    is_emerging: bool = False
    dashboard_label: str = ""


class TrendsDashboardResponse(BaseModel):
    generated_at: datetime
    window_days: int
    emerging_destinations: List[EmergingDestinationTrend]
    summary: str = ""


class SeasonalPattern(BaseModel):
    label: str
    intensity: float = Field(..., ge=0.0, le=1.0)
    months_peak: List[int] = Field(default_factory=list)


class SegmentBehaviorInsight(BaseModel):
    segment_id: str
    segment_label: str
    seasonal_patterns: List[SeasonalPattern]
    budget_profile: Dict[str, Any] = Field(default_factory=dict)
    top_preferences: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class SegmentInsightsResponse(BaseModel):
    generated_at: datetime
    insights: SegmentBehaviorInsight


class MicroTrendOpportunity(BaseModel):
    trend_id: str
    title: str
    affected_segments: List[str] = Field(default_factory=list)
    opportunity_score: float = Field(..., ge=0.0, le=1.0)
    suggested_action: str = ""


class PartnerTrendNotification(BaseModel):
    notification_id: str
    target_partner_profile: str = Field(
        ...,
        description="Hint de segmento de empresa (p.ej. touroperadores premium)",
    )
    micro_trend_id: str
    message: str
    weekly_cycle_anchor: str = Field(..., description="ISO week label for weekly refresh (PBI 31)")


class WeeklyTrendsDigestResponse(BaseModel):
    generated_at: datetime
    micro_trends: List[MicroTrendOpportunity]
    partner_notifications: List[PartnerTrendNotification]
    next_refresh_note: str = "Análisis programable semanal (sustituir por job + cola en producción)."
