"""
Chat-specific Pydantic schemas.

These types define the public API contract for the /api/v1/chat endpoints
and the internal data structures shared across chat sub-components.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

class ChatIntent(str, Enum):
    """Classified intent of a user message."""
    GREETING = "greeting"
    TRAVEL_PLANNING = "travel_planning"
    BUDGET_QUESTION = "budget_question"
    ACTIVITY_QUERY = "activity_query"
    DESTINATION_QUERY = "destination_query"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Travel context — accumulated across conversation turns
# ---------------------------------------------------------------------------

class TravelContext(BaseModel):
    """
    Accumulated travel planning context for a single user session.

    Updated incrementally as the user reveals more information across turns.
    Aligned with the backend TravelPlan domain model.
    """
    destination: Optional[str] = None            # maps to TravelPlan.destinationLocation
    origin: Optional[str] = None                 # maps to TravelPlan.originLocation
    budget_usd: Optional[float] = None           # maps to TravelPlan.estimatedBudget
    duration_days: Optional[int] = None          # derived from startDate/endDate delta
    group_size: Optional[int] = Field(default=1) # maps to TravelPlan.numberOfTravelers
    travel_style: Optional[str] = None           # maps to TravelPlan.travelType
    interests: List[str] = Field(default_factory=list)  # maps to User.interests
    activity_types: List[str] = Field(default_factory=list)  # preferred ActivityType values
    start_date: Optional[str] = None             # ISO date string
    end_date: Optional[str] = None               # ISO date string
    # Keyword frequency counters for proactive suggestion triggers
    keyword_counts: Dict[str, int] = Field(default_factory=dict)

    def merge(self, other: "TravelContext") -> "TravelContext":
        """
        Merge another (partial) context into this one.

        Fields in `other` take precedence only when they are non-None / non-empty.
        Keyword counts are accumulated across merges.
        """
        result = self.model_copy()
        if other.destination:
            result.destination = other.destination
        if other.origin:
            result.origin = other.origin
        if other.budget_usd is not None:
            result.budget_usd = other.budget_usd
        if other.duration_days is not None:
            result.duration_days = other.duration_days
        if other.group_size and other.group_size > 1:
            result.group_size = other.group_size
        if other.travel_style:
            result.travel_style = other.travel_style
        if other.interests:
            # Union: add new interests, preserve existing
            result.interests = list(set(result.interests) | set(other.interests))
        if other.activity_types:
            result.activity_types = list(set(result.activity_types) | set(other.activity_types))
        if other.start_date:
            result.start_date = other.start_date
        if other.end_date:
            result.end_date = other.end_date
        # Accumulate keyword counts
        for kw, count in other.keyword_counts.items():
            result.keyword_counts[kw] = result.keyword_counts.get(kw, 0) + count
        return result


# ---------------------------------------------------------------------------
# Conversation message (history entry)
# ---------------------------------------------------------------------------

class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: str                   # "user" | "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: Optional[ChatIntent] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v


# ---------------------------------------------------------------------------
# Suggestion — structured recommendation from the engine
# ---------------------------------------------------------------------------

class Suggestion(BaseModel):
    """
    A single structured activity or destination suggestion.
    Produced by ChatRecommendationEngine and consumed by the reply builders.
    """
    name: str
    activity_type: str                        # ActivityType value
    description: str
    estimated_cost_usd: Optional[float] = None
    duration_hours: Optional[float] = None
    budget_tier: Optional[str] = None        # "budget", "mid-range", "premium"
    tags: List[str] = Field(default_factory=list)
    is_proactive: bool = False               # True if surfaced by ProactiveEngine


# ---------------------------------------------------------------------------
# API request / response contracts
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Input to POST /api/v1/chat."""
    userId: str = Field(..., min_length=1, description="Unique user identifier")
    message: str = Field(..., min_length=1, max_length=2000, description="User message text")

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped

    @field_validator("userId")
    @classmethod
    def user_id_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("userId must not be blank")
        return v.strip()


class ChatResponse(BaseModel):
    """Output from POST /api/v1/chat."""
    reply: str
    suggestions: List[Suggestion] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationHistoryResponse(BaseModel):
    """Output from GET /api/v1/chat/{userId}/history."""
    userId: str
    messages: List[ConversationMessage]
    context: TravelContext
    total_messages: int


class ClearHistoryResponse(BaseModel):
    """Output from DELETE /api/v1/chat/{userId}/history."""
    userId: str
    message: str
    cleared_at: datetime = Field(default_factory=datetime.utcnow)
