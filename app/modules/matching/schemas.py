"""Schemas for traveler matching, compatibility scores, and learning outcomes.

Purpose:
    Support matching API requests/responses and connection-outcome callbacks.

Dependencies:
    ``Location``, ``ConnectionOutcome``, ``TravelPreference``.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import ConnectionOutcome, TravelPreference


class TravelerMatchRequest(BaseModel):
    """Criteria to search for compatible travel partners."""

    user_id: str
    location: Location
    travel_dates: Optional[Dict[str, str]] = None
    preferences: Optional[List[TravelPreference]] = None
    max_matches: int = 10


class TravelerMatch(BaseModel):
    """One ranked candidate with compatibility breakdown."""

    user_id: str
    name: str
    age: Optional[int] = None
    compatibility_score: float
    common_preferences: List[TravelPreference] = Field(default_factory=list)
    travel_style_match: float
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    dimension_summary: Optional[Dict[str, float]] = None
    shared_destinations: List[str] = Field(default_factory=list)


class MatchingResponse(BaseModel):
    """Collection of matches returned to the client."""

    matches: List[TravelerMatch]
    user_id: str
    generated_at: datetime
    total_matches: int
    search_criteria: Dict[str, Any] = Field(default_factory=dict)


class ConnectionOutcomeRequest(BaseModel):
    """Report how a connection attempt resolved for weight learning."""

    user_id: str
    target_user_id: str
    outcome: ConnectionOutcome
    dimension_snapshot: Optional[Dict[str, float]] = None
    notes: Optional[str] = None


class ConnectionOutcomeResponse(BaseModel):
    """Acknowledgement after recording a connection outcome."""

    status: str
    updated_weights: Dict[str, float]


class MatchingProfile(BaseModel):
    user_id: str
    name: str
    age: Optional[int] = None
    location: Optional[str] = None
    preferences: List[TravelPreference] = Field(default_factory=list)
    travel_style: str = "mid-range"
    budget_tier: str = "mid"
    pace: str = "moderate"
    personality_tags: List[str] = Field(default_factory=list)
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    travel_footprint: List[str] = Field(default_factory=list)


class MatchingProfilesIngestRequest(BaseModel):
    profiles: List[MatchingProfile] = Field(min_length=1)
