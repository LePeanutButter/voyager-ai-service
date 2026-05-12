"""Prompt templates for budget adjustment with an LLM.

Purpose:
    Guide the model to acknowledge budget changes and recalibrate recommendations.

Responsibilities:
    Expose ``SYSTEM_PROMPT`` and ``render_budget_adjustment_prompt`` with spend bands.

Dependencies:
    ``TravelContext`` (conditional typing only).
"""
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.chat.schemas import TravelContext


SYSTEM_PROMPT = """You are an expert AI travel planning assistant for the Voyager platform.
A user has just updated their travel budget. Your job is to:
1. Acknowledge the budget change warmly
2. Explain how this affects their trip options
3. Provide adjusted activity recommendations within the new budget
4. Be honest about trade-offs (e.g., fewer premium experiences vs more local ones)

Keep the response practical and positive. Never shame the user for their budget.
"""


def render_budget_adjustment_prompt(
    user_message: str,
    context: "TravelContext",
    old_budget_usd: Optional[float],
    new_budget_usd: float,
) -> str:
    """Builds the user prompt after a budget change is detected.

    Args:
        user_message: Message that triggered the update.
        context: Context already updated with the new budget.
        old_budget_usd: Previous value, or ``None`` if none.
        new_budget_usd: New amount in USD.

    Returns:
        String with ``## Budget Update`` blocks and user message.
    """
    budget_change_desc = (
        f"Changed from ${old_budget_usd:,.0f} to ${new_budget_usd:,.0f}"
        if old_budget_usd is not None
        else f"Newly set to ${new_budget_usd:,.0f}"
    )

    tier = _budget_tier(new_budget_usd)
    destination = context.destination or "their destination"
    duration = f"{context.duration_days} days" if context.duration_days else "their trip"

    return (
        f"## Budget Update\n"
        f"- {budget_change_desc}\n"
        f"- Budget tier: {tier}\n"
        f"- Destination: {destination}\n"
        f"- Duration: {duration}\n"
        f"- Group size: {context.group_size or 1}\n"
        f"\n## User Message\n{user_message}\n\n"
        "Please provide budget-adjusted travel recommendations."
    )


def _budget_tier(budget_usd: float) -> str:
    """Describes the qualitative budget band for the prompt.

    Args:
        budget_usd: Amount in USD (non-null).

    Returns:
        Text label with range and spending-style hints.
    """
    if budget_usd < 300:
        return "very budget (<$300) — hostels, street food, free attractions"
    if budget_usd < 500:
        return "budget ($300–$500) — guesthouses, local restaurants, select paid attractions"
    if budget_usd < 1000:
        return "economy ($500–$1000) — 2-star hotels, mix of free and paid activities"
    if budget_usd < 2000:
        return "mid-range ($1000–$2000) — 3-star hotels, comfortable experiences"
    if budget_usd < 5000:
        return "upper mid-range ($2000–$5000) — 4-star hotels, guided tours"
    return "premium (>$5,000) — luxury hotels, exclusive experiences"
