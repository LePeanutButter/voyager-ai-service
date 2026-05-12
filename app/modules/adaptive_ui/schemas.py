"""Pydantic schemas for adaptive UI responses (menu and feed).

Purpose:
    Type navigation items, menu adaptation responses, and home sections.

Dependencies:
    ``pydantic``, ``NavItemTier`` from shared enums.
"""

from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field

from app.modules.common.schemas.enums import NavItemTier


class MenuNavItem(BaseModel):
    """Menu entry with priority and human-readable explanation for the client.

    Important attributes:
        nav_item_id: Stable id aligned with the service catalog.
        tier: Primary or secondary level from recent usage.
        usage_score: Relative frequency in the analysis window.
    """

    nav_item_id: str
    label: str
    sort_index: int = 0
    tier: NavItemTier = NavItemTier.PRIMARY
    usage_score: float = Field(0.0, ge=0.0, le=1.0, description="Normalized 0–1 from frequency in window")
    adaptation_reason: str = ""


class MenuAdaptationResponse(BaseModel):
    """Full navigation reordering payload for a user."""

    user_id: str
    generated_at: datetime
    analysis_window_days: int = 30
    primary_items: List[MenuNavItem] = Field(default_factory=list)
    secondary_items: List[MenuNavItem] = Field(default_factory=list)
    summary: str = ""


class HomeFeedSection(BaseModel):
    """Feed content block with weight and theme tags."""

    section_id: str
    title: str
    content_types: List[str] = Field(
        default_factory=list,
        description="e.g. destinations, activities, stories",
    )
    theme_tags: List[str] = Field(
        default_factory=list,
        description="Aligned with interests: adventure, cultural, etc.",
    )
    priority_weight: float = Field(..., ge=0.0, le=1.0)


class HomeFeedLayoutResponse(BaseModel):
    """Home layout derived from recent behavior signals."""

    user_id: str
    generated_at: datetime
    primary_theme: str = Field(
        default="balanced",
        description="Main hero / spotlight theme (e.g. adventure, cultural).",
    )
    sections: List[HomeFeedSection] = Field(default_factory=list)
    recommendation_theme_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Suggested per-theme weighting for next recommendation calls.",
    )
    feed_refresh_note: str = (
        "Priorities from recent behavior; "
        "refresh when new interactions arrive (PBI 33)."
    )
