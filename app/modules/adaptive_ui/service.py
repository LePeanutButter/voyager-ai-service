"""Behavior-driven adaptive UI service (Feature 16, PBI 32–33).

Purpose:
    Reorder the menu and compose home sections from interactions stored in the
    same in-memory store as ``BehaviorAnalysisService``.

Responsibilities:
    Weight ``nav_item_id`` in tracking context, derive feed themes from activity
    categories, and apply configurable cultural boosting.

Dependencies:
    ``BehaviorAnalysisService``, ``settings``, ``NavItemTier`` and
    ``TravelPreference`` enums, response schemas in ``schemas``.

Note:
    Clients should send ``context.nav_item_id`` on behavior tracking POST for menu
    adaptation; categories feed the home layout.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.modules.common.schemas.enums import NavItemTier, TravelPreference
from app.modules.adaptive_ui.schemas import (
    HomeFeedLayoutResponse,
    HomeFeedSection,
    MenuAdaptationResponse,
    MenuNavItem,
)
from app.modules.behavior.service import BehaviorAnalysisService

logger = logging.getLogger(__name__)

# Fixed navigation catalog (frontend resolves routes).
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

# Activity / interaction category → feed theme and TravelPreference mapping
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
    """Scales positive weights to [0, 1] by dividing by the maximum.

    Args:
        raw: Counters or weights per theme.

    Returns:
        Empty dict if no input; otherwise values rounded to four decimals.
    """
    if not raw:
        return {}
    m = max(raw.values()) or 1.0
    return {k: round(v / m, 4) for k, v in raw.items()}


class AdaptiveUIService:
    """Computes personalized menu and feed from the user's recent interactions.

    Important attributes:
        _behavior: Reference to the shared behavior analysis service.
    """

    def __init__(self, behavior_service: BehaviorAnalysisService) -> None:
        self._behavior = behavior_service

    @staticmethod
    def _catalog_order(nav_id: str) -> int:
        for entry in _NAV_CATALOG:
            if entry["id"] == nav_id:
                return entry["default_order"]
        return 99

    @staticmethod
    def _nav_label(nav_id: str) -> str:
        return next((entry["label"] for entry in _NAV_CATALOG if entry["id"] == nav_id), nav_id)

    @staticmethod
    def _interaction_weight(item: Dict[str, Any]) -> float:
        interaction = item.get("interaction_type")
        if interaction is None:
            return 1.0
        name = getattr(interaction, "value", str(interaction))
        if name == "click":
            return 2.0
        if name == "view":
            return 1.0
        return 1.0

    def _build_nav_counts(self, interactions: List[Dict[str, Any]]) -> Counter[str]:
        nav_counts: Counter[str] = Counter()
        for item in interactions:
            ctx = item.get("context") or {}
            nav_item_id = ctx.get("nav_item_id")
            if isinstance(nav_item_id, str) and nav_item_id:
                nav_counts[nav_item_id] += self._interaction_weight(item)
        return nav_counts

    @staticmethod
    def _tier_for_nav(
        nav_id: str,
        count: float,
        no_nav_signal: bool,
        primary_len: int,
        primary_cap: int,
        top_count: float,
        window: int,
    ) -> tuple[NavItemTier, str]:
        if no_nav_signal:
            if primary_len < primary_cap:
                return NavItemTier.PRIMARY, "Orden por defecto (sin datos de uso de menú en la ventana)."
            return NavItemTier.SECONDARY, "Resto de entradas en menú secundario o “más”."
        if count == 0:
            reason = (
                f"Sin accesos en los últimos {window} días; "
                "mostrar en menú secundario o “más”."
            )
            return NavItemTier.SECONDARY, reason
        if primary_len < primary_cap:
            if nav_id == "matching" and top_count > 0 and count >= top_count * 0.25:
                return NavItemTier.PRIMARY, "Uso frecuente de Matching — prioridad en barra principal."
            return NavItemTier.PRIMARY, "Priorizado por frecuencia de uso en la ventana."
        return NavItemTier.SECONDARY, "Fuera del top de slots primarios; agrupar en secundario."

    @staticmethod
    def _assign_sort_indexes(items: List[MenuNavItem]) -> None:
        for idx, item in enumerate(items):
            item.sort_index = idx

    @staticmethod
    def _menu_summary(interactions: List[Dict[str, Any]]) -> str:
        if not interactions:
            return (
                "Sin interacciones recientes; orden por defecto. "
                "Enviar `context.nav_item_id` en POST /behavior-analysis/track."
            )
        return (
            "Menú adaptado por `nav_item_id` en el contexto de tracking. "
            "Sin datos: orden por defecto y todo en primarios hasta límite de slots."
        )

    def _interactions_in_window(
        self, user_id: str, days: int
    ) -> List[Dict[str, Any]]:
        """Filters user interactions after the UTC time cutoff.

        Args:
            user_id: User identifier.
            days: Lookback window in days.

        Returns:
            List of interaction dicts or empty list if none.
        """
        return self._behavior.get_recent_interactions(user_id=user_id, days=days)

    def build_menu_adaptation(self, user_id: str) -> MenuAdaptationResponse:
        """Builds primary and secondary menu items from ``nav_item_id`` frequency.

        Args:
            user_id: Target user.

        Returns:
            Response with order, tiers, scores, and summary text for the client.
        """
        window = settings.ADAPTIVE_UI_ANALYSIS_WINDOW_DAYS
        interactions = self._interactions_in_window(user_id, window)
        nav_counts = self._build_nav_counts(interactions)

        max_count = max(nav_counts.values(), default=0)
        scored_ids = [e["id"] for e in _NAV_CATALOG]
        scored_ids.sort(key=lambda x: (-nav_counts.get(x, 0), self._catalog_order(x)))

        primary_cap = settings.ADAPTIVE_UI_PRIMARY_NAV_SLOTS
        primary: List[MenuNavItem] = []
        secondary: List[MenuNavItem] = []
        no_nav_signal = max_count == 0
        top_count = max_count

        for nav_id in scored_ids:
            label = self._nav_label(nav_id)
            count = nav_counts.get(nav_id, 0)
            usage_score = float(count / max_count) if max_count > 0 else 0.0
            tier, reason = self._tier_for_nav(
                nav_id=nav_id,
                count=count,
                no_nav_signal=no_nav_signal,
                primary_len=len(primary),
                primary_cap=primary_cap,
                top_count=top_count,
                window=window,
            )

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

        self._assign_sort_indexes(primary)
        self._assign_sort_indexes(secondary)
        summary = self._menu_summary(interactions)

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
        """Aggregates weights per theme from activity categories and interest context.

        Args:
            interactions: Events already filtered by time window.

        Returns:
            Theme → accumulated weight map (not normalized).
        """
        weights: Dict[str, float] = defaultdict(float)
        for item in interactions:
            self._add_category_weight(weights, item)
            self._add_context_weights(weights, item.get("context") or {})

        return dict(weights)

    @staticmethod
    def _theme_weight_for_interaction(interaction: Any) -> float:
        name = getattr(interaction, "value", str(interaction)) if interaction is not None else ""
        if name in ("bookmark", "book", "rate"):
            return 1.5
        if name == "click":
            return 1.2
        if name == "view":
            return 0.8
        return 1.0

    def _add_category_weight(self, weights: Dict[str, float], item: Dict[str, Any]) -> None:
        category = item.get("activity_category")
        if not category:
            return
        theme = _CATEGORY_TO_THEME.get(str(category).lower())
        if not theme:
            return
        weights[theme] += self._theme_weight_for_interaction(item.get("interaction_type"))

    @staticmethod
    def _add_context_weights(weights: Dict[str, float], context: Dict[str, Any]) -> None:
        for pref in TravelPreference:
            key = f"interest_{pref.value}"
            if context.get(key) or context.get("theme") == pref.value:
                weights[pref.value] += 1.0

    def build_home_feed_layout(self, user_id: str) -> HomeFeedLayoutResponse:
        """Composes home sections and weights for thematic recommendations.

        Args:
            user_id: Target user.

        Returns:
            Layout with per-theme sections or default balanced layout without signals.
        """
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

        # Cultural boost after cultural interactions (PBI 33)
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
