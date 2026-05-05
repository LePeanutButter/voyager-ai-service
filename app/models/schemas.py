"""
**Deprecated** — use ``app.modules.<domain>.schemas`` or ``app.modules.common.schemas``.

Re-exports preserve compatibility for external imports of ``app.models.schemas``
until callers migrate.
"""

from app.modules.adaptive_ui.schemas import (
    HomeFeedLayoutResponse,
    HomeFeedSection,
    MenuAdaptationResponse,
    MenuNavItem,
)
from app.modules.behavior.schemas import (
    BehaviorAnalysisRequest,
    BehaviorPattern,
    BehaviorTrackingRequest,
    ImplicitPreferenceUpdate,
)
from app.modules.common.schemas import (
    APIResponse,
    ActivityType,
    ConnectionOutcome,
    DateRange,
    InteractionType,
    Location,
    NavItemTier,
    TravelPreference,
    WeatherCondition,
)
from app.modules.matching.schemas import (
    ConnectionOutcomeRequest,
    ConnectionOutcomeResponse,
    MatchingResponse,
    TravelerMatch,
    TravelerMatchRequest,
)
from app.modules.recommendations.schemas import (
    Activity,
    ContextualActivityRequest,
    ContextualActivityResponse,
    DestinationCard,
    DestinationRecommendationRequest,
    DestinationRecommendationResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from app.modules.trends.schemas import (
    EmergingDestinationTrend,
    MicroTrendOpportunity,
    PartnerTrendNotification,
    SeasonalPattern,
    SegmentBehaviorInsight,
    SegmentInsightsResponse,
    TrendsDashboardResponse,
    WeeklyTrendsDigestResponse,
)
from app.modules.users.schemas import (
    UserInteraction,
    UserPreferences,
    UserProfile,
    UserProfileUpdate,
)

__all__ = [
    "APIResponse",
    "Activity",
    "ActivityType",
    "BehaviorAnalysisRequest",
    "BehaviorPattern",
    "BehaviorTrackingRequest",
    "ConnectionOutcome",
    "ConnectionOutcomeRequest",
    "ConnectionOutcomeResponse",
    "ContextualActivityRequest",
    "ContextualActivityResponse",
    "DateRange",
    "DestinationCard",
    "DestinationRecommendationRequest",
    "DestinationRecommendationResponse",
    "EmergingDestinationTrend",
    "HomeFeedLayoutResponse",
    "HomeFeedSection",
    "ImplicitPreferenceUpdate",
    "InteractionType",
    "Location",
    "MatchingResponse",
    "MenuAdaptationResponse",
    "MenuNavItem",
    "MicroTrendOpportunity",
    "NavItemTier",
    "PartnerTrendNotification",
    "RecommendationRequest",
    "RecommendationResponse",
    "SeasonalPattern",
    "SegmentBehaviorInsight",
    "SegmentInsightsResponse",
    "TrendsDashboardResponse",
    "TravelPreference",
    "TravelerMatch",
    "TravelerMatchRequest",
    "UserInteraction",
    "UserPreferences",
    "UserProfile",
    "UserProfileUpdate",
    "WeatherCondition",
    "WeeklyTrendsDigestResponse",
]
