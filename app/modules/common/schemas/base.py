"""Shared base Pydantic models (location, generic response, date range).

Responsibilities:
    Define reusable DTOs for routers and services without coupling to a specific domain.

Dependencies:
    `pydantic.BaseModel`, `datetime`.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Geographic coordinates and metadata for radius searches.

    Attributes:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        city: Optional city hint.
        country: Optional country.
        radius_km: Search radius in kilometers.
    """

    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    radius_km: float = 10.0


class APIResponse(BaseModel):
    """Generic success/error wrapper for simple payloads.

    Attributes:
        success: Whether the operation succeeded logically.
        message: Human-readable message for the client.
        data: Arbitrary payload or None.
    """

    success: bool = True
    message: str = ""
    data: Optional[Any] = None


class DateRange(BaseModel):
    """Inclusive time interval for analysis or filters.

    Attributes:
        start: Range start.
        end: Range end.
    """

    start: datetime
    end: datetime
