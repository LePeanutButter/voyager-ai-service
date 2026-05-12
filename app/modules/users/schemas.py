"""User domain models for profiles, preferences, and interaction events.

Purpose:
    Type API payloads for user CRUD and analytics fed by the users router.

Dependencies:
    ``TravelPreference`` enum from common schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.common.schemas.enums import TravelPreference


class UserPreferences(BaseModel):
    """Structured travel and accessibility preferences for a user."""

    preferences: List[TravelPreference] = Field(default_factory=list)
    budget_range: Dict[str, float] = Field(default_factory=lambda: {"min": 50, "max": 200})
    travel_style: str = "mid-range"
    group_size: int = 2
    accessibility_needs: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)
    language_preferences: List[str] = Field(default_factory=lambda: ["English"])


class UserProfile(BaseModel):
    """Full user record including preferences and travel history metadata."""

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
    """Partial update payload for merging into an existing profile."""

    preferences: Optional[UserPreferences] = None
    location: Optional[str] = None
    travel_history: Optional[List[Dict[str, Any]]] = None


class UserInteraction(BaseModel):
    """Recorded interaction for profiling or recommendation feedback."""

    user_id: str
    activity_id: str
    interaction_type: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
