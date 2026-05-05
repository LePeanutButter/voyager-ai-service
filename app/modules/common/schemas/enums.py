from enum import Enum


class TravelPreference(str, Enum):
    CULTURAL = "cultural"
    FOODIE = "foodie"
    ADVENTURE = "adventure"
    NATURE = "nature"
    RELAXATION = "relaxation"
    BEACH = "beach"


class ActivityType(str, Enum):
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
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    SNOW = "snow"
    EXTREME_HEAT = "extreme_heat"
    UNKNOWN = "unknown"


class ConnectionOutcome(str, Enum):
    SUCCESS = "success"
    INCOMPATIBLE = "incompatible"


class InteractionType(str, Enum):
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
    PRIMARY = "primary"
    SECONDARY = "secondary"
    OVERFLOW = "overflow"
