from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import ConnectionOutcome, TravelPreference


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


class ConnectionOutcomeRequest(BaseModel):
    user_id: str
    target_user_id: str
    outcome: ConnectionOutcome
    dimension_snapshot: Optional[Dict[str, float]] = None
    notes: Optional[str] = None


class ConnectionOutcomeResponse(BaseModel):
    status: str
    updated_weights: Dict[str, float]
