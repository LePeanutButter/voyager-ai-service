"""
Shared Pydantic schemas for the Tourism Assistant API.

Feature coverage (agile backlog):
- F12 PBI 24–25: destinations + contextual activities
- F13 PBI 26–27: multidimensional matching + continuous learning payloads
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TravelPreference(str, Enum):
    CULTURAL = "cultural"
    FOODIE = "foodie"
    ADVENTURE = "adventure"
    NATURE = "nature"
    RELAXATION = "relaxation"
    BEACH = "beach"


class ActivityType(str, Enum):
    CULTURAL = "cultural"
    OUTDOOR = "outdoor"
    FOOD = "food"
    ENTERTAINMENT = "entertainment"
    WELLNESS = "wellness"
    SHOPPING = "shopping"
    NIGHTLIFE = "nightlife"
    SPORTS = "sports"
    EDUCATION = "education"


class Location(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    radius_km: float = 10.0


class UserPreferences(BaseModel):
    preferences: List[TravelPreference] = Field(default_factory=list)
    budget_range: Dict[str, float] = Field(default_factory=lambda: {"min": 50, "max": 200})
    travel_style: str = "mid-range"
    group_size: int = 2
    accessibility_needs: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    language_preferences: List[str] = Field(default_factory=lambda: ["English"])


class UserProfile(BaseModel):
    user_id: str
    name: str
    email: str
    age: Optional[int] = None
    location: Optional[str] = None
    preferences: UserPreferences
    travel_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserProfileUpdate(BaseModel):
    preferences: Optional[UserPreferences] = None
    location: Optional[str] = None
    travel_history: Optional[List[Dict[str, Any]]] = None


class UserInteraction(BaseModel):
    user_id: str
    activity_id: str
    interaction_type: str  # view, like, save, book, dismiss
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class RecommendationRequest(BaseModel):
    user_id: str
    location: Location
    preferences: Optional[List[TravelPreference]] = None
    max_results: int = 10
    date_range: Optional[Dict[str, str]] = None
    group_size: Optional[int] = None
    budget_limit: Optional[float] = None


class Activity(BaseModel):
    activity_id: str
    name: str
    category: ActivityType
    description: str
    location: Location
    rating: float
    price_range: str
    duration_hours: float
    tags: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list)
    best_time_to_visit: str = "Any time"
    images: List[str] = Field(default_factory=list)
    indoor: bool = False
    distance_km: Optional[float] = None


class RecommendationResponse(BaseModel):
    recommendations: List[Activity]
    user_id: str
    generated_at: datetime
    total_results: int
    confidence_scores: List[float] = Field(default_factory=list)
    explanation: str = ""


class TravelerMatchRequest(BaseModel):
    user_id: str
    location: Location
    travel_dates: Optional[Dict[str, str]] = None
    preferences: Optional[List[TravelPreference]] = None
    max_matches: int = 10


class TravelerMatch(BaseModel):
    user_id: str
    name: str
    age: Optional[int] = None
    compatibility_score: float
    common_preferences: List[TravelPreference] = Field(default_factory=list)
    travel_style_match: float
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    dimension_summary: Optional[Dict[str, float]] = None


class MatchingResponse(BaseModel):
    matches: List[TravelerMatch]
    user_id: str
    generated_at: datetime
    total_matches: int
    search_criteria: Dict[str, Any] = Field(default_factory=dict)


class APIResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[Any] = None


# --- Feature 12: destinations (PBI 24) & contextual activities (PBI 25) ---


class DestinationCard(BaseModel):
    destination_id: str
    name: str
    country: str
    tags: List[str] = Field(default_factory=list)
    compatibility_score: float = Field(..., ge=0.0, le=1.0)
    rationale: str = ""


class DestinationRecommendationRequest(BaseModel):
    user_id: str
    max_results: int = 8
    """If True, bias toward categories seen in successful past trips while keeping variety."""
    prefer_successful_patterns: bool = True
    """PBI 30: merge destinations marcados como emergentes si encajan con preferencias."""
    include_emerging_trends: bool = True


class DestinationRecommendationResponse(BaseModel):
    user_id: str
    destinations: List[DestinationCard]
    generated_at: datetime
    diversity_note: str = ""


class WeatherCondition(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    EXTREME_HEAT = "extreme_heat"
    UNKNOWN = "unknown"


class ContextualActivityRequest(BaseModel):
    user_id: str
    latitude: float
    longitude: float
    city_hint: Optional[str] = None
    weather: WeatherCondition = WeatherCondition.UNKNOWN
    max_results: int = 8
    radius_km: float = 25.0


class ContextualActivityResponse(BaseModel):
    user_id: str
    location_summary: str
    weather: WeatherCondition
    activities: List[Activity]
    context_adjustment: str = ""
    generated_at: datetime


# --- Feature 13: matching learning (PBI 27) ---


class ConnectionOutcome(str, Enum):
    SUCCESS = "success"
    INCOMPATIBLE = "incompatible"


class ConnectionOutcomeRequest(BaseModel):
    user_id: str
    target_user_id: str
    outcome: ConnectionOutcome
    """Optional snapshot of dimension scores at match time (for reinforcement)."""
    dimension_snapshot: Optional[Dict[str, float]] = None
    notes: Optional[str] = None


class ConnectionOutcomeResponse(BaseModel):
    status: str
    updated_weights: Dict[str, float]


# --- Feature 15: predictive trends (PBI 30–31) ---


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
    """Listo para mostrar en dashboard de tendencias."""
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
