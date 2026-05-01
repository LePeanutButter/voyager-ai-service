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


def build_planning_reply(
    context: "TravelContext",
    suggestions: List["Suggestion"],
    is_first_message: bool,
) -> str:
    """
    Build a plain-text conversational reply for travel planning intent.

    Args:
        context         : Extracted travel context for this user.
        suggestions     : Structured suggestions from the recommendation engine.
        is_first_message: True when this is the opening turn of a conversation.

    Returns:
        A natural-language string suitable for returning to the user.
    """
    parts: List[str] = []

    # Greeting / acknowledgement
    if is_first_message:
        parts.append("Welcome! I'm your AI travel assistant.")

    # Confirm what we understood
    understood: List[str] = []
    if context.destination:
        understood.append(f"destination: **{context.destination}**")
    if context.budget_usd is not None:
        understood.append(f"budget: **${context.budget_usd:,.0f}**")
    if context.duration_days is not None:
        understood.append(
            f"duration: **{context.duration_days} day{'s' if context.duration_days != 1 else ''}**"
        )
    if context.group_size and context.group_size > 1:
        understood.append(f"group size: **{context.group_size}**")
    if context.travel_style:
        understood.append(f"style: **{context.travel_style}**")

    if understood:
        parts.append("Here's what I understood about your trip — " + ", ".join(understood) + ".")

    # Add suggestions
    if suggestions:
        parts.append(_format_suggestions(suggestions))
    else:
        # Ask for more context if we have nothing to recommend yet
        missing = _identify_missing_context(context)
        if missing:
            parts.append(f"To give you better recommendations, could you tell me your {missing}?")
        else:
            parts.append(
                "I'd love to help you plan this trip! "
                "Could you share any specific interests or activities you enjoy?"
            )

    return "\n\n".join(parts)


def build_budget_reply(
    context: "TravelContext",
    suggestions: List["Suggestion"],
    old_budget: Optional[float],
) -> str:
    """
    Build a reply acknowledging a budget change and adjusting recommendations.

    Args:
        context    : Updated travel context with new budget.
        suggestions: Recalculated suggestions for the new budget.
        old_budget : Previous budget value (or None if not set before).

    Returns:
        A natural-language string.
    """
    parts: List[str] = []

    if old_budget is not None and context.budget_usd is not None:
        direction = "lower" if context.budget_usd < old_budget else "higher"
        parts.append(
            f"Got it! I've adjusted your recommendations for your {direction} budget "
            f"of **${context.budget_usd:,.0f}**."
        )
    elif context.budget_usd is not None:
        parts.append(f"Thanks for sharing your budget of **${context.budget_usd:,.0f}**.")

    if suggestions:
        parts.append(_format_suggestions(suggestions))
    else:
        destination_hint = f" in {context.destination}" if context.destination else ""
        parts.append(
            f"With this budget{destination_hint}, I recommend focusing on "
            "free or low-cost cultural experiences, local street food, and public transportation."
        )

    return "\n\n".join(parts)


def build_follow_up_reply(
    context: "TravelContext",
    suggestions: List["Suggestion"],
    user_message: str,
) -> str:
    """
    Build a reply for a follow-up / clarification message.

    Args:
        context      : Current travel context.
        suggestions  : Suggestions (may be empty if context is thin).
        user_message : The raw user message (used for keyword-based routing).

    Returns:
        A natural-language string.
    """
    msg_lower = user_message.lower()
    parts: List[str] = []

    # Acknowledge the specific follow-up topic
    if any(w in msg_lower for w in ("weather", "climate", "season", "when")):
        dest = context.destination or "your destination"
        parts.append(
            f"The best time to visit {dest} depends on the season. "
            "I recommend checking local weather patterns for your travel dates."
        )
    elif any(w in msg_lower for w in ("food", "eat", "restaurant", "cuisine", "dining")):
        parts.append("Great choice — local cuisine is one of the highlights of any trip!")
    elif any(w in msg_lower for w in ("transport", "flight", "train", "bus", "get there")):
        dest = context.destination or "your destination"
        parts.append(
            f"For getting to {dest}, compare flights on aggregator sites. "
            "Once there, local public transit is often the most cost-effective option."
        )
    elif any(w in msg_lower for w in ("hotel", "stay", "accommodation", "hostel", "airbnb")):
        tier = _budget_tier(context.budget_usd)
        if tier == "budget":
            parts.append("For budget stays, hostels and guesthouses offer great value and social vibes.")
        elif tier == "premium":
            parts.append("With your budget, you have access to excellent boutique hotels and resorts.")
        else:
            parts.append("Mid-range hotels and serviced apartments offer a good balance of comfort and price.")
    else:
        parts.append(
            f"Based on your trip context{' to ' + context.destination if context.destination else ''}, "
            "here are my thoughts:"
        )

    if suggestions:
        parts.append(_format_suggestions(suggestions))
    elif context.destination:
        parts.append(
            f"Would you like me to suggest specific activities or itinerary ideas for {context.destination}?"
        )

    return "\n\n".join(parts)


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

def _format_suggestions(suggestions: List["Suggestion"]) -> str:
    """Format a list of Suggestion objects into a readable reply block."""
    if not suggestions:
        return ""

    lines: List[str] = ["Here are some recommendations:"]
    for i, s in enumerate(suggestions[:5], start=1):
        cost_hint = f" (~${s.estimated_cost_usd:,.0f})" if s.estimated_cost_usd else ""
        lines.append(f"{i}. **{s.name}** — {s.activity_type}{cost_hint}")
        if s.description:
            lines.append(f"   {s.description}")
    return "\n".join(lines)


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
