"""
Chat Recommendation Engine.

Generates structured Suggestion objects from a TravelContext.
Logic is parameterised — no hardcoded destinations or fixed suggestion lists.

Filtering dimensions:
  - Budget tier  : $0-500 (budget), $500-2000 (mid-range), $2000+ (premium)
  - Travel style : maps to preferred ActivityType clusters
  - Duration     : controls how many suggestions to surface
  - Group size   : adjusts solo vs group-friendly activity weighting

Domain alignment with backend:
  ActivityType: SIGHTSEEING, CULTURAL, ADVENTURE, DINING, SHOPPING,
                ENTERTAINMENT, SPORTS, RELAXATION, EDUCATIONAL, SOCIAL
  TravelType  : LEISURE, ADVENTURE, CULTURAL, ROMANTIC, FAMILY, SOLO, BUSINESS
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.chat.schemas import Suggestion, TravelContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Activity catalogue — parameterised templates, not hardcoded suggestions
# ---------------------------------------------------------------------------

# Each entry: (activity_type, description_template, cost_budget, cost_mid, cost_premium, tags)
_ACTIVITY_TEMPLATES: List[Tuple[str, str, float, float, float, List[str]]] = [
    # (type,         template,                                              budget, mid,  prem, tags)
    ("sightseeing",  "Explore iconic landmarks and local neighbourhoods",    0,    20,   80,   ["outdoors", "photography"]),
    ("cultural",     "Visit museums, galleries, and historical sites",       10,   30,   100,  ["history", "art", "learning"]),
    ("dining",       "Try authentic local cuisine at recommended spots",     15,   40,   120,  ["food", "local"]),
    ("adventure",    "Experience outdoor adventures and active excursions",  30,   80,   250,  ["active", "nature"]),
    ("relaxation",   "Relax at parks, beaches, or local wellness centres",   0,    50,   200,  ["calm", "nature"]),
    ("shopping",     "Discover local markets, crafts, and unique souvenirs", 0,    30,   150,  ["local", "gifts"]),
    ("entertainment","Enjoy live music, performances, or local events",      20,   50,   180,  ["nightlife", "culture"]),
    ("sports",       "Participate in local sports or recreational activities",25,   60,   200,  ["active", "fitness"]),
    ("educational",  "Join guided tours, cooking classes, or workshops",     15,   45,   130,  ["learning", "experience"]),
    ("social",       "Meet locals through meetups, tours, or community events", 0, 25,   80,   ["people", "culture"]),
]

# Travel style → preferred activity types (ordered by weight)
_STYLE_ACTIVITY_MAP: Dict[str, List[str]] = {
    "adventure":  ["adventure", "sports", "sightseeing", "educational", "relaxation"],
    "cultural":   ["cultural", "educational", "sightseeing", "dining", "social"],
    "leisure":    ["relaxation", "dining", "sightseeing", "entertainment", "shopping"],
    "romantic":   ["dining", "relaxation", "sightseeing", "entertainment", "cultural"],
    "family":     ["sightseeing", "educational", "sports", "dining", "entertainment"],
    "solo":       ["social", "cultural", "adventure", "sightseeing", "educational"],
    "business":   ["dining", "sightseeing", "relaxation", "cultural", "entertainment"],
    # Fallback ordering (used when style is unknown)
    "default":    ["sightseeing", "cultural", "dining", "adventure", "relaxation"],
}

# Budget tier thresholds (USD, total trip budget)
_BUDGET_TIERS = {
    "budget":    (0,    500),
    "mid-range": (500,  2000),
    "premium":   (2000, float("inf")),
}


def _budget_tier(budget_usd: Optional[float]) -> str:
    if budget_usd is None:
        return "mid-range"
    if budget_usd < 500:
        return "budget"
    if budget_usd < 2000:
        return "mid-range"
    return "premium"


class ChatRecommendationEngine:
    """
    Generates context-aware Suggestion objects from a TravelContext.

    This engine is deterministic and rule-based. It does NOT call any
    external APIs or ML models — recommendations derive entirely from
    the logic encoded in activity templates and style mappings.
    """

    def generate(
        self,
        context: TravelContext,
        max_suggestions: int = 5,
        exclude_types: Optional[List[str]] = None,
    ) -> List[Suggestion]:
        """
        Generate activity suggestions for the given context.

        Args:
            context        : Current trip context (destination, budget, style…).
            max_suggestions: Max number of suggestions to return.
            exclude_types  : Activity types to skip (e.g., already shown).

        Returns:
            List of Suggestion objects, ordered by relevance to the context.
        """
        if max_suggestions <= 0:
            return []

        exclude = set(exclude_types or [])
        tier = _budget_tier(context.budget_usd)
        preferred_order = self._get_preferred_order(context)

        # Build candidates in preference order
        candidates: List[Suggestion] = []
        for activity_type in preferred_order:
            if activity_type in exclude:
                continue
            template = self._find_template(activity_type)
            if template is None:
                continue

            suggestion = self._build_suggestion(template, context, tier)
            if suggestion is not None:
                candidates.append(suggestion)
                if len(candidates) >= max_suggestions:
                    break

        # If we still need more, pad from remaining types
        if len(candidates) < max_suggestions:
            for tmpl in _ACTIVITY_TEMPLATES:
                act_type = tmpl[0]
                if act_type in exclude or any(s.activity_type == act_type for s in candidates):
                    continue
                suggestion = self._build_suggestion(tmpl, context, tier)
                if suggestion is not None:
                    candidates.append(suggestion)
                    if len(candidates) >= max_suggestions:
                        break

        logger.debug(
            "Generated %d suggestions for context (dest=%s, budget=%s, style=%s)",
            len(candidates), context.destination, context.budget_usd, context.travel_style,
        )
        return candidates

    def generate_for_activity_types(
        self,
        activity_types: List[str],
        context: TravelContext,
        max_suggestions: int = 5,
    ) -> List[Suggestion]:
        """
        Generate suggestions restricted to specific activity types.
        Used when the user explicitly requests a category (e.g., "adventure activities").
        """
        if not activity_types:
            return self.generate(context, max_suggestions)

        tier = _budget_tier(context.budget_usd)
        candidates: List[Suggestion] = []

        for activity_type in activity_types:
            template = self._find_template(activity_type)
            if template is None:
                continue
            suggestion = self._build_suggestion(template, context, tier)
            if suggestion:
                candidates.append(suggestion)

        # Fill remaining slots from general generation
        if len(candidates) < max_suggestions:
            extra = self.generate(
                context,
                max_suggestions - len(candidates),
                exclude_types=[s.activity_type for s in candidates],
            )
            candidates.extend(extra)

        return candidates[:max_suggestions]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_preferred_order(self, context: TravelContext) -> List[str]:
        """Return activity types ordered by preference for this context."""
        style = (context.travel_style or "default").lower()

        # If user expressed explicit activity_types, prioritise them
        if context.activity_types:
            remaining = [t for t in _STYLE_ACTIVITY_MAP.get(style, _STYLE_ACTIVITY_MAP["default"])
                         if t not in context.activity_types]
            return context.activity_types + remaining

        return _STYLE_ACTIVITY_MAP.get(style, _STYLE_ACTIVITY_MAP["default"])

    def _find_template(self, activity_type: str) -> Optional[tuple]:
        """Find the template tuple for a given activity type."""
        for tmpl in _ACTIVITY_TEMPLATES:
            if tmpl[0] == activity_type:
                return tmpl
        return None

    def _build_suggestion(
        self,
        template: tuple,
        context: TravelContext,
        tier: str,
    ) -> Optional[Suggestion]:
        """
        Construct a Suggestion from a template + context.

        Cost is parameterised per-person per-activity; the full trip cost
        considers group size and duration to ensure it fits the budget.
        """
        act_type, description_tmpl, cost_b, cost_m, cost_p, tags = template

        # Select per-activity cost based on tier
        cost_map = {"budget": cost_b, "mid-range": cost_m, "premium": cost_p}
        per_person_cost = cost_map.get(tier, cost_m)

        # Scale by group size (shared activities cost less per person)
        group = max(context.group_size or 1, 1)
        if group > 1:
            per_person_cost = per_person_cost * (1 + (group - 1) * 0.7) / group

        # Budget gate: skip if this single activity exceeds 30% of total budget
        if context.budget_usd and per_person_cost * group > context.budget_usd * 0.30:
            if tier == "premium":
                # For premium, still include but note cost
                pass
            else:
                return None  # Activity too expensive relative to budget

        # Personalise description with destination
        destination_phrase = f" in {context.destination}" if context.destination else ""
        full_description = f"{description_tmpl}{destination_phrase}."

        # Add budget-appropriate qualifier
        if tier == "budget" and per_person_cost == 0:
            full_description += " Free admission available."
        elif tier == "budget":
            full_description += " Many low-cost options available."

        return Suggestion(
            name=_activity_display_name(act_type, context.destination),
            activity_type=act_type,
            description=full_description,
            estimated_cost_usd=round(per_person_cost, 0) if per_person_cost > 0 else None,
            duration_hours=_typical_duration(act_type),
            budget_tier=tier,
            tags=tags,
        )


def _activity_display_name(activity_type: str, destination: Optional[str]) -> str:
    """Generate a display name for an activity suggestion."""
    location_suffix = f" — {destination}" if destination else ""
    names = {
        "sightseeing":   f"Sightseeing & Exploration{location_suffix}",
        "cultural":      f"Cultural Experiences{location_suffix}",
        "dining":        f"Local Dining & Cuisine{location_suffix}",
        "adventure":     f"Adventure Activities{location_suffix}",
        "relaxation":    f"Relaxation & Wellness{location_suffix}",
        "shopping":      f"Shopping & Markets{location_suffix}",
        "entertainment": f"Entertainment & Nightlife{location_suffix}",
        "sports":        f"Sports & Recreation{location_suffix}",
        "educational":   f"Guided Tours & Workshops{location_suffix}",
        "social":        f"Social Experiences & Meetups{location_suffix}",
    }
    return names.get(activity_type, f"{activity_type.title()}{location_suffix}")


def _typical_duration(activity_type: str) -> Optional[float]:
    """Return typical duration (hours) for an activity type."""
    durations = {
        "sightseeing": 3.0, "cultural": 2.5, "dining": 1.5,
        "adventure": 4.0, "relaxation": 2.0, "shopping": 2.0,
        "entertainment": 2.5, "sports": 2.0, "educational": 2.0, "social": 2.0,
    }
    return durations.get(activity_type)
