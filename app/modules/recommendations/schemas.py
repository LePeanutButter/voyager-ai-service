from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import ActivityType, TravelPreference, WeatherCondition


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
    prefer_successful_patterns: bool = True
    include_emerging_trends: bool = True
    theme_weights: Optional[Dict[str, float]] = None


class DestinationRecommendationResponse(BaseModel):
    user_id: str
    destinations: List[DestinationCard]
    generated_at: datetime
    diversity_note: str = ""


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
