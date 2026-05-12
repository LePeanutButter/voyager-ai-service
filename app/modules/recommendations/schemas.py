"""Schemas for personalized activities, destinations, and contextual listings.

Purpose:
    Define contracts for recommendation endpoints including geo-contextual queries.

Dependencies:
    ``Location``, ``ActivityType``, ``TravelPreference``, ``WeatherCondition``.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import ActivityType, TravelPreference, WeatherCondition
from app.modules.seasonality.schemas import SeasonalContext


class RecommendationRequest(BaseModel):
    """Standard recommendation query for a user near a location."""

    user_id: str
    location: Location
    preferences: Optional[List[TravelPreference]] = None
    max_results: int = 10
    date_range: Optional[Dict[str, str]] = None
    group_size: Optional[int] = None
    budget_limit: Optional[float] = None


class Activity(BaseModel):
    """Rich activity card returned in recommendation lists."""

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
    """Batch of activities with optional confidence and explanation."""

    recommendations: List[Activity]
    user_id: str
    generated_at: datetime
    total_results: int
    confidence_scores: List[float] = Field(default_factory=list)
    explanation: str = ""


class DestinationCard(BaseModel):
    """Destination suggestion with compatibility score and rationale text."""

    destination_id: str
    name: str
    country: str
    tags: List[str] = Field(default_factory=list)
    compatibility_score: float = Field(..., ge=0.0, le=1.0)
    rationale: str = ""
    seasonal_context: Optional[SeasonalContext] = None


class DestinationRecommendationRequest(BaseModel):
    """Request for personalized destination cards."""

    user_id: str
    max_results: int = 8
    prefer_successful_patterns: bool = True
    include_emerging_trends: bool = True
    theme_weights: Optional[Dict[str, float]] = None
    travel_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Mes previsto del viaje (1–12); por defecto mes actual UTC.",
    )
    apply_seasonality_mitigation: bool = Field(
        default=True,
        description="Aplica mitigación de estacionalidad al ranking (paper: visibilidad dinámica).",
    )


class DestinationRecommendationResponse(BaseModel):
    """Ranked destinations with optional diversity note."""

    user_id: str
    destinations: List[DestinationCard]
    generated_at: datetime
    diversity_note: str = ""
    seasonality_note: str = ""


class ContextualActivityRequest(BaseModel):
    """Nearby activity query with optional weather for indoor/outdoor logic."""

    user_id: str
    latitude: float
    longitude: float
    city_hint: Optional[str] = None
    weather: WeatherCondition = WeatherCondition.UNKNOWN
    max_results: int = 8
    radius_km: float = 25.0


class ContextualActivityResponse(BaseModel):
    """Activities adjusted to current place and weather context."""

    user_id: str
    location_summary: str
    weather: WeatherCondition
    activities: List[Activity]
    context_adjustment: str = ""
    generated_at: datetime
