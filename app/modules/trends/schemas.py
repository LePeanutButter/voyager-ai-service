"""Pydantic schemas for travel trends, segments, and weekly digest.

Purpose:
    Model emerging destinations, segment insights, and partner notifications.

Dependencies:
    ``pydantic``, standard ``datetime`` and collection types.
"""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class EmergingDestinationTrend(BaseModel):
    """Aggregated interest volume series and emerging classification."""

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
    """Panel view with filtered emerging destinations and text summary."""

    generated_at: datetime
    window_days: int
    emerging_destinations: List[EmergingDestinationTrend]
    summary: str = ""


class SeasonalPattern(BaseModel):
    """Seasonal pattern with peak months and normalized intensity."""

    label: str
    intensity: float = Field(..., ge=0.0, le=1.0)
    months_peak: List[int] = Field(default_factory=list)


class SegmentBehaviorInsight(BaseModel):
    """Predictive behavior snapshot for a traveler segment."""

    segment_id: str
    segment_label: str
    seasonal_patterns: List[SeasonalPattern]
    budget_profile: Dict[str, Any] = Field(default_factory=dict)
    top_preferences: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class SegmentInsightsResponse(BaseModel):
    """Wrapper with generation metadata and a single insight."""

    generated_at: datetime
    insights: SegmentBehaviorInsight


class MicroTrendOpportunity(BaseModel):
    """Business opportunity from a detected micro-trend."""

    trend_id: str
    title: str
    affected_segments: List[str] = Field(default_factory=list)
    opportunity_score: float = Field(..., ge=0.0, le=1.0)
    suggested_action: str = ""


class PartnerTrendNotification(BaseModel):
    """Message to a partner profile with weekly anchor."""

    notification_id: str
    target_partner_profile: str = Field(
        ...,
        description="Company segment hint (e.g. premium tour operators)",
    )
    micro_trend_id: str
    message: str
    weekly_cycle_anchor: str = Field(..., description="ISO week label for weekly refresh (PBI 31)")


class WeeklyTrendsDigestResponse(BaseModel):
    """Weekly digest with micro-trends and simulated commercial notices."""

    generated_at: datetime
    micro_trends: List[MicroTrendOpportunity]
    partner_notifications: List[PartnerTrendNotification]
    next_refresh_note: str = "Schedulable weekly analysis (replace with job + queue in production)."


class TrendSignalIngestRow(BaseModel):
    destination_id: str
    name: str
    country: str
    tags: List[str] = Field(default_factory=list)
    previous: int = Field(ge=0)
    current: int = Field(ge=0)


class TrendSignalIngestRequest(BaseModel):
    rows: List[TrendSignalIngestRow] = Field(min_length=1)


class TrendSegmentsIngestRequest(BaseModel):
    segments: Dict[str, Any] = Field(min_length=1)
