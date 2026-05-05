from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field

from app.modules.common.schemas.enums import NavItemTier


class MenuNavItem(BaseModel):
    nav_item_id: str
    label: str
    sort_index: int = 0
    tier: NavItemTier = NavItemTier.PRIMARY
    usage_score: float = Field(0.0, ge=0.0, le=1.0, description="Normalizado 0–1 según frecuencia en la ventana")
    adaptation_reason: str = ""


class MenuAdaptationResponse(BaseModel):
    user_id: str
    generated_at: datetime
    analysis_window_days: int = 30
    primary_items: List[MenuNavItem] = Field(default_factory=list)
    secondary_items: List[MenuNavItem] = Field(default_factory=list)
    summary: str = ""


class HomeFeedSection(BaseModel):
    section_id: str
    title: str
    content_types: List[str] = Field(
        default_factory=list,
        description="p.ej. destinations, activities, stories",
    )
    theme_tags: List[str] = Field(
        default_factory=list,
        description="Alineado con intereses: adventure, cultural, etc.",
    )
    priority_weight: float = Field(..., ge=0.0, le=1.0)


class HomeFeedLayoutResponse(BaseModel):
    user_id: str
    generated_at: datetime
    primary_theme: str = Field(
        default="balanced",
        description="Tema principal del hero / destacados (p.ej. adventure, cultural).",
    )
    sections: List[HomeFeedSection] = Field(default_factory=list)
    recommendation_theme_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Ponderación sugerida por tema para siguientes llamadas a recomendaciones.",
    )
    feed_refresh_note: str = (
        "Prioridades derivadas del comportamiento reciente; "
        "actualizar al recibir nuevas interacciones (PBI 33)."
    )
