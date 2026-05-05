"""Pydantic models for behavior tracking and implicit preference inference.

Purpose:
    Define request/response contracts for the behavior-analysis API and
    structured outputs from pattern detection.

Dependencies:
    ``DateRange``, ``InteractionType`` from common schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.common.schemas.base import DateRange
from app.modules.common.schemas.enums import InteractionType


class BehaviorTrackingRequest(BaseModel):
    """Single user interaction to persist for later analysis."""

    user_id: str
    interaction_type: InteractionType
    activity_id: Optional[str] = None
    activity_category: Optional[str] = None
    session_duration: Optional[float] = None
    context: Optional[Dict[str, Any]] = None


class BehaviorAnalysisRequest(BaseModel):
    """Parameters for an on-demand behavior analysis run."""

    user_id: str
    analysis_period_days: int = 7
    include_patterns: bool = True
    include_preference_updates: bool = True


class BehaviorPattern(BaseModel):
    """Detected recurring signal (rejection streak, category affinity, etc.)."""

    pattern_type: str
    confidence: float
    frequency: int
    last_detected: datetime
    context: Dict[str, Any] = Field(default_factory=dict)


class ImplicitPreferenceUpdate(BaseModel):
    """Aggregated result of a behavior analysis pass for one user."""

    user_id: str
    preference_changes: Dict[str, float]
    detected_patterns: List[BehaviorPattern]
    analysis_period: DateRange
    confidence_score: float
