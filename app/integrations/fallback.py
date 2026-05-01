"""
Rule-based fallback responder.

Used when LLM_PROVIDER == "none" or when all LLM calls fail.
Generates coherent, context-aware travel responses using deterministic
logic derived from the extracted TravelContext — no hardcoded strings,
no fake AI.

All public methods mirror the signature expectations of ChatService so
they are drop-in replacements for LLM-generated content.
"""

import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.chat.schemas import TravelContext, Suggestion

logger = logging.getLogger(__name__)


def _format_destinations(dests: List["Suggestion"]) -> str:
    if not dests:
        return ""
    d = dests[0]
    return f"• **Top Recommendation: {d.name}**\n  {d.description}"


def _format_activities(acts: List["Suggestion"], context: "TravelContext") -> str:
    if not acts:
        return ""
        
    parts = []
    days_dict = {}
    others = []
    for s in acts:
        if s.name.startswith("Day "):
            try:
                day_num, act_name = s.name.split(":", 1)
                day_num = day_num.strip()
                act_name = act_name.strip()
                if day_num not in days_dict:
                    days_dict[day_num] = []
                days_dict[day_num].append((act_name, s))
            except ValueError:
                others.append(s)
        else:
            others.append(s)

    for day_num, day_acts in days_dict.items():
        parts.append(f"\n{day_num}:")
        for act_name, s in day_acts:
            cost_str = "(free)"
            if s.estimated_cost_usd and s.estimated_cost_usd > 0:
                suffix = " per person" if context.group_size and context.group_size > 1 else ""
                cost_str = f"(~${s.estimated_cost_usd:,.0f}{suffix})"
            parts.append(f"- {act_name} {cost_str}")

    if others:
        parts.append("")
        for s in others:
            cost_str = "(free)"
            if s.estimated_cost_usd and s.estimated_cost_usd > 0:
                suffix = " per person" if context.group_size and context.group_size > 1 else ""
                cost_str = f"(~${s.estimated_cost_usd:,.0f}{suffix})"
            parts.append(f"- {s.name} {cost_str}")

    return "\n".join(parts)


def _format_itinerary(suggestions: List["Suggestion"], context: "TravelContext") -> str:
    if not suggestions:
        return ""

    dests = [s for s in suggestions if s.activity_type == "destination"]
    acts = [s for s in suggestions if s.activity_type != "destination"]

    parts = []
    
    dest_str = _format_destinations(dests)
    if dest_str:
        parts.append(dest_str)
        
    acts_str = _format_activities(acts, context)
    if acts_str:
        parts.append(acts_str)

    return "\n".join(parts).strip()


def _build_intro_string(context: "TravelContext") -> str:
    intro_words = []
    if context.duration_days:
        intro_words.append(f"a {context.duration_days}-day")
    else:
        intro_words.append("a")

    if context.budget_usd is not None:
        if context.budget_usd < 500:
            intro_words.append("low-budget")
        elif context.budget_usd > 2000:
            intro_words.append("premium")
    elif context.travel_style:
        intro_words.append(context.travel_style)

    intro_words.append("trip")

    if context.destination:
        intro_words.append(f"to {context.destination}")

    if context.group_size and context.group_size == 2:
        intro_words.append("with your partner")
    elif context.group_size and context.group_size > 2:
        intro_words.append(f"for {context.group_size} people")
    elif context.group_size == 1 or context.travel_style == "solo":
        intro_words.append("solo")

    return " ".join(intro_words)


def build_planning_reply(
    context: "TravelContext",
    suggestions: List["Suggestion"],
) -> str:
    """Build a reply for a travel planning intent."""
    parts = []

    intro_str = _build_intro_string(context)

    if suggestions:
        parts.append(f"For {intro_str}:\n")
        parts.append(_format_itinerary(suggestions, context))
    else:
        missing = _identify_missing_context(context)
        if missing:
            parts.append(f"To give you better recommendations, could you tell me your {missing}?")
        else:
            parts.append("Could you share any specific interests or activities you enjoy?")

    return "\n".join(parts)


def build_budget_reply(
    context: "TravelContext",
    suggestions: List["Suggestion"],
    old_budget: Optional[float],
) -> str:
    """Build a reply acknowledging a budget constraint update."""
    parts = []

    if old_budget is not None and context.budget_usd is not None:
        direction = "lower" if context.budget_usd < old_budget else "higher"
        parts.append(
            f"Got it! I've adjusted your recommendations for your {direction} budget "
            f"of **${context.budget_usd:,.0f}**.\n"
        )
    elif context.budget_usd is not None:
        parts.append(f"Thanks for sharing your budget of **${context.budget_usd:,.0f}**.\n")

    if suggestions:
        parts.append(_format_itinerary(suggestions, context))
    else:
        parts.append("I don't have specific recommendations for this budget yet.")

    return "\n".join(parts)


def build_follow_up_reply(
    context: "TravelContext",
    suggestions: List["Suggestion"],
    user_message: str,
) -> str:
    """Build a generic follow-up reply."""
    msg_lower = user_message.lower()
    parts = []

    if any(kw in msg_lower for kw in ("food", "eat", "dining", "restaurant")):
        parts.append("I see you're interested in food and dining!")
    elif any(kw in msg_lower for kw in ("museum", "history", "culture")):
        parts.append("Cultural and historical activities are a great choice.")
    elif any(kw in msg_lower for kw in ("adventure", "hike", "active")):
        parts.append("Adventure activities are a great way to explore!")
    else:
        dest_str = f" to {context.destination}" if context.destination else ""
        parts.append(f"Based on your trip context{dest_str}, here are my thoughts:")

    if suggestions:
        parts.append("\nHere are some recommendations:\n")
        parts.append(_format_itinerary(suggestions, context))
    elif context.destination:
        parts.append(
            f"\nWould you like me to suggest specific activities for {context.destination}?"
        )

    return "\n".join(parts)


def build_greeting_reply() -> str:
    """Return a welcoming introduction message."""
    return (
        "Hello! I'm your AI travel planning assistant. 🌍\n\n"
        "I can help you:\n"
        "• Plan a trip to any destination\n"
        "• Find activities that match your budget and style\n"
        "• Suggest itineraries based on your interests\n"
        "• Adjust recommendations as your plans evolve\n\n"
        "Just tell me where you'd like to go, your budget, and how many days you have — "
        "and we'll start planning!"
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _identify_missing_context(context: "TravelContext") -> str:
    """Return a human-readable list of missing context fields."""
    missing: List[str] = []
    if not context.destination:
        missing.append("destination")
    if context.budget_usd is None:
        missing.append("budget")
    if context.duration_days is None:
        missing.append("trip duration")
    return " and ".join(missing)


def _budget_tier(budget_usd: Optional[float]) -> str:
    """Classify budget as 'budget', 'mid-range', or 'premium'."""
    if budget_usd is None:
        return "mid-range"
    if budget_usd < 500:
        return "budget"
    if budget_usd < 2000:
        return "mid-range"
    return "premium"
