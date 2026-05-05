from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = None
    country: Optional[str] = None
    radius_km: float = 10.0


class APIResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[Any] = None


class DateRange(BaseModel):
    start: datetime
    end: datetime
