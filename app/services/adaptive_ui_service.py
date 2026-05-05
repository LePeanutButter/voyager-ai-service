"""
Feature 16 — UI adaptativa según comportamiento (PBI 32–33).

Usa el mismo almacenamiento in-memory que BehaviorAnalysisService. El cliente debe
enviar en `context` de POST /behavior-analysis/track el campo `nav_item_id` para
adaptación de menú (y categorías en interacciones para el feed).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.schemas import (
    HomeFeedLayoutResponse,
    HomeFeedSection,
    MenuAdaptationResponse,
    MenuNavItem,
    NavItemTier,
    TravelPreference,
)
from app.services.behavior_analysis_service import BehaviorAnalysisService

logger = logging.getLogger(__name__)

# Catálogo fijo de entradas de navegación (el front resuelve rutas).
_NAV_CATALOG: List[Dict[str, Any]] = [
    {"id": "home", "label": "Inicio", "default_order": 0},
    {"id": "discover", "label": "Descubrir", "default_order": 1},
    {"id": "matching", "label": "Matching", "default_order": 2},
    {"id": "trips", "label": "Mis viajes", "default_order": 3},
    {"id": "chat", "label": "Asistente", "default_order": 4},
    {"id": "bookmarks", "label": "Guardados", "default_order": 5},
    {"id": "profile", "label": "Perfil", "default_order": 6},
    {"id": "preferences", "label": "Preferencias", "default_order": 7},
]

# Mapeo categoría de actividad / interacción → tema de feed y TravelPreference
_CATEGORY_TO_THEME: Dict[str, str] = {
    "cultural": "cultural",
    "adventure": "adventure",
    "outdoor": "adventure",
    "food": "foodie",
    "foodie": "foodie",
    "nature": "nature",
    "beach": "beach",
    "relaxation": "relaxation",
    "wellness": "relaxation",
    "entertainment": "cultural",
    "education": "cultural",
    "sports": "adventure",
    "nightlife": "cultural",
    "shopping": "cultural",
}


def _normalize_weights(raw: Dict[str, float]) -> Dict[str, float]:
    if not raw:
        return {}
    m = max(raw.values()) or 1.0
    return {k: round(v / m, 4) for k, v in raw.items()}


class AdaptiveUIService:
    """Reordena menú y compone secciones del home según interacciones recientes."""

    def __init__(self, behavior_service: BehaviorAnalysisService) -> None:
        self._behavior = behavior_service

    def _interactions_in_window(
        self, user_id: str, days: int
    ) -> List[Dict[str, Any]]:
        if user_id not in self._behavior.behavior_data:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        interactions = self._behavior.behavior_data[user_id]["interactions"]
        return [i for i in interactions if i["timestamp"] > cutoff]

    def build_menu_adaptation(self, user_id: str) -> MenuAdaptationResponse:
        window = settings.ADAPTIVE_UI_ANALYSIS_WINDOW_DAYS
        interactions = self._interactions_in_window(user_id, window)

        nav_counts: Counter[str] = Counter()
        for item in interactions:
            ctx = item.get("context") or {}
            nid = ctx.get("nav_item_id")
            if isinstance(nid, str) and nid:
                w = 1.0
                it = item.get("interaction_type")
                if it is not None:
                    name = getattr(it, "value", str(it))
                    if name == "click":
                        w = 2.0
                    elif name == "view":
                        w = 1.0
                nav_counts[nid] += w

        max_count = max(nav_counts.values(), default=0)

        # Orden: primero por uso descendente; empate por default_order del catálogo
        def catalog_order(nav_id: str) -> int:
            for e in _NAV_CATALOG:
                if e["id"] == nav_id:
                    return e["default_order"]
            return 99

        scored_ids = [e["id"] for e in _NAV_CATALOG]
        scored_ids.sort(
            key=lambda x: (-nav_counts.get(x, 0), catalog_order(x))
        )

        primary_cap = settings.ADAPTIVE_UI_PRIMARY_NAV_SLOTS
        primary: List[MenuNavItem] = []
        secondary: List[MenuNavItem] = []
        # Sin señales de navegación: barra por defecto (primeros slots del catálogo)
        no_nav_signal = max_count == 0

        for nav_id in scored_ids:
            label = next(
                (e["label"] for e in _NAV_CATALOG if e["id"] == nav_id), nav_id
            )
            count = nav_counts.get(nav_id, 0)
            usage_score = float(count / max_count) if max_count > 0 else 0.0

            if no_nav_signal:
                if len(primary) < primary_cap:
                    tier = NavItemTier.PRIMARY
                    reason = "Orden por defecto (sin datos de uso de menú en la ventana)."
                else:
                    tier = NavItemTier.SECONDARY
                    reason = "Resto de entradas en menú secundario o “más”."
            # Sin uso en la ventana → secundario / agrupado (PBI 32)
            elif count == 0:
                tier = NavItemTier.SECONDARY
                reason = (
                    f"Sin accesos en los últimos {window} días; "
                    "mostrar en menú secundario o “más”."
                )
            elif len(primary) < primary_cap:
                tier = NavItemTier.PRIMARY
                top_count = max(nav_counts.values()) if nav_counts else 0
                if nav_id == "matching" and top_count > 0 and count >= top_count * 0.25:
                    reason = (
                        "Uso frecuente de Matching — prioridad en barra principal."
                    )
                else:
                    reason = "Priorizado por frecuencia de uso en la ventana."
            else:
                tier = NavItemTier.SECONDARY
                reason = "Fuera del top de slots primarios; agrupar en secundario."

            entry = MenuNavItem(
                nav_item_id=nav_id,
                label=label,
                sort_index=len(primary) if tier == NavItemTier.PRIMARY else len(secondary),
                tier=tier,
                usage_score=round(usage_score, 4),
                adaptation_reason=reason,
            )
            if tier == NavItemTier.PRIMARY:
                primary.append(entry)
            else:
                secondary.append(entry)

        # Re-asignar sort_index secuencial
        for i, p in enumerate(primary):
            p.sort_index = i
        for i, s in enumerate(secondary):
            s.sort_index = i

        summary = (
            "Menú adaptado por `nav_item_id` en el contexto de tracking. "
            "Sin datos: orden por defecto y todo en primarios hasta límite de slots."
        )
        if not interactions:
            summary = (
                "Sin interacciones recientes; orden por defecto. "
                "Enviar `context.nav_item_id` en POST /behavior-analysis/track."
            )

        return MenuAdaptationResponse(
            user_id=user_id,
            generated_at=datetime.now(timezone.utc),
            analysis_window_days=window,
            primary_items=primary,
            secondary_items=secondary,
            summary=summary,
        )

    def _theme_signals_from_interactions(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        weights: Dict[str, float] = defaultdict(float)
        for item in interactions:
            cat = item.get("activity_category")
            if cat:
                theme = _CATEGORY_TO_THEME.get(str(cat).lower(), None)
                if theme:
                    w = 1.0
                    it = item.get("interaction_type")
                    name = getattr(it, "value", str(it)) if it is not None else ""
                    if name in ("bookmark", "book", "rate"):
                        w = 1.5
                    elif name == "click":
                        w = 1.2
                    elif name == "view":
                        w = 0.8
                    weights[theme] += w

            ctx = item.get("context") or {}
            for pref in TravelPreference:
                key = f"interest_{pref.value}"
                if ctx.get(key) or ctx.get("theme") == pref.value:
                    weights[pref.value] += 1.0

        return dict(weights)

    def build_home_feed_layout(self, user_id: str) -> HomeFeedLayoutResponse:
        window = settings.ADAPTIVE_UI_ANALYSIS_WINDOW_DAYS
        interactions = self._interactions_in_window(user_id, window)
        themes = self._theme_signals_from_interactions(interactions)
        normalized = _normalize_weights(themes)

        if not normalized:
            default_sections = [
                HomeFeedSection(
                    section_id="spotlight",
                    title="Destacados para ti",
                    content_types=["destinations", "activities"],
                    theme_tags=["cultural", "adventure", "nature"],
                    priority_weight=0.5,
                ),
                HomeFeedSection(
                    section_id="discover",
                    title="Descubre más",
                    content_types=["destinations"],
                    theme_tags=["foodie", "relaxation", "beach"],
                    priority_weight=0.35,
                ),
            ]
            return HomeFeedLayoutResponse(
                user_id=user_id,
                generated_at=datetime.now(timezone.utc),
                primary_theme="balanced",
                sections=default_sections,
                recommendation_theme_weights={},
                feed_refresh_note=(
                    "Sin señales de tema; feed equilibrado. "
                    "Interacciones con `activity_category` alimentan priorización."
                ),
            )

        sorted_themes = sorted(normalized.items(), key=lambda x: -x[1])
        primary_theme = sorted_themes[0][0]

        sections: List[HomeFeedSection] = []
        for i, (theme, w) in enumerate(sorted_themes[:5]):
            title = {
                "adventure": "Aventura y outdoor",
                "cultural": "Cultura y arte",
                "foodie": "Gastronomía",
                "nature": "Naturaleza",
                "beach": "Playa y costa",
                "relaxation": "Relax y bienestar",
            }.get(theme, theme.title())
            sections.append(
                HomeFeedSection(
                    section_id=f"theme_{theme}_{i}",
                    title=title,
                    content_types=["destinations", "activities", "stories"],
                    theme_tags=[theme],
                    priority_weight=round(w, 4),
                )
            )

        # Refuerzo cultural tras interacciones culturales (PBI 33)
        boost_note = ""
        if normalized.get("cultural", 0) >= 0.35:
            normalized["cultural"] = min(
                1.0, normalized.get("cultural", 0) + settings.ADAPTIVE_UI_THEME_BOOST_DELTA
            )
            boost_note = " Refuerzo aplicado a experiencias culturales."

        return HomeFeedLayoutResponse(
            user_id=user_id,
            generated_at=datetime.now(timezone.utc),
            primary_theme=primary_theme,
            sections=sections,
            recommendation_theme_weights=_normalize_weights(normalized),
            feed_refresh_note=(
                "Ponderación lista para la siguiente recomendación; "
                "actualizar al refrescar el feed."
                + boost_note
            ),
        )
