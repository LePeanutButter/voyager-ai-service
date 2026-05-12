"""Shared enumerations (preferences, activity types, weather, etc.).

Responsibilities:
    Centralize valid values aligned with the travel and tracking domain.

Dependencies:
    Standard library `enum` only.
"""

from enum import Enum


class TravelPreference(str, Enum):
    """Travel preference axis for the user."""

    CULTURAL = "cultural"
    FOODIE = "foodie"
    ADVENTURE = "adventure"
    NATURE = "nature"
    RELAXATION = "relaxation"
    BEACH = "beach"


class ActivityType(str, Enum):
    """Tourism activity category."""

    CULTURAL = "cultural"
    OUTDOOR = "outdoor"
    FOOD = "food"
    ENTERTAINMENT = "entertainment"
    WELLNESS = "wellness"
    SHOPPING = "shopping"
    NIGHTLIFE = "nightlife"
    SPORTS = "sports"
    EDUCATION = "education"


class WeatherCondition(str, Enum):
    """Weather condition for contextual recommendations."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    EXTREME_HEAT = "extreme_heat"
    UNKNOWN = "unknown"


class ConnectionOutcome(str, Enum):
    """Explicit outcome after interacting with a match (learning)."""

    SUCCESS = "success"
    INCOMPATIBLE = "incompatible"


class InteractionType(str, Enum):
    """User behavior event type."""

    VIEW = "view"
    CLICK = "click"
    BOOKMARK = "bookmark"
    SHARE = "share"
    REJECT = "reject"
    BOOK = "book"
    RATE = "rate"
    SEARCH = "search"
    FILTER = "filter"


class NavItemTier(str, Enum):
    """Prominence level of an adaptive navigation item."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    OVERFLOW = "overflow"
