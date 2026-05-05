"""Re-exports common types (base DTOs and enums) for shorter imports.

Responsibilities:
    Centralize `__all__` with public symbols from `base` and `enums`.

Dependencies:
    `app.modules.common.schemas.base`, `app.modules.common.schemas.enums`.
"""

from app.modules.common.schemas.base import APIResponse, DateRange, Location
from app.modules.common.schemas.enums import (
    ActivityType,
    ConnectionOutcome,
    InteractionType,
    NavItemTier,
    TravelPreference,
    WeatherCondition,
)

__all__ = [
    "APIResponse",
    "ActivityType",
    "ConnectionOutcome",
    "DateRange",
    "InteractionType",
    "Location",
    "NavItemTier",
    "TravelPreference",
    "WeatherCondition",
]
