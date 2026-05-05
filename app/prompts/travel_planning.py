"""
Travel planning prompt template.

Defines the system prompt and initial user-message prompt for the main
travel planning conversation. Used when an LLM provider is active.

The system prompt instructs the model on:
  - Its role and personality
  - Output format expectations (markdown, structured when needed)
  - Domain constraints (budget awareness, activity types)
  - What NOT to do (hallucinate bookings, claim real-time data)
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.chat.schemas import TravelContext


SYSTEM_PROMPT = """You are an expert AI travel planning assistant for the Voyager platform.

## Your Role
Help users plan personalised, budget-aware travel itineraries through natural conversation.
You maintain context across multiple messages and progressively refine recommendations.

## Domain Knowledge
You understand:
- Travel plan components: destination, budget, dates, group size, travel style
- Activity types: sightseeing, cultural, adventure, dining, shopping, entertainment,
  sports, relaxation, educational, social
- Travel styles: leisure, adventure, cultural, romantic, family, solo, business
- Budget tiers: budget (<$500), mid-range ($500–$2000), premium (>$2000)

## Communication Style
- Be conversational, warm, and concise
- Use markdown formatting (bold destinations, bullet points for activity lists)
- Always acknowledge what the user told you before giving recommendations
- Ask clarifying questions when context is missing (destination, budget, or duration)
- Never invent specific hotel names, flight prices, or booking references

## Output Constraints
- Keep replies under 400 words unless the user asks for a detailed itinerary
- If generating a day-by-day itinerary, use a clear Day 1 / Day 2 structure
- When budget is tight, always prioritise free or low-cost activities first
- Mention estimated costs where relevant (use ranges, not exact prices)
"""


def render_planning_prompt(
    user_message: str,
    context: "TravelContext",
    history_summary: Optional[str] = None,
) -> str:
    """
    Build the user-facing prompt for a travel planning request.

    Args:
        user_message    : The raw user message.
        context         : Current extracted travel context.
        history_summary : Optional 1-2 sentence summary of prior conversation.

    Returns:
        Formatted prompt string to send as the user turn.
    """
    context_block = _render_context_block(context)
    history_block = f"\n## Conversation So Far\n{history_summary}\n" if history_summary else ""

    return (
        f"{context_block}"
        f"{history_block}"
        f"\n## User Message\n{user_message}\n\n"
        "Please respond as the travel assistant."
    )


def _render_context_block(context: "TravelContext") -> str:
    """Render a structured context block from TravelContext."""
    lines = ["## Current Trip Context"]
    lines.append(f"- Destination: {context.destination or 'Not specified'}")
    lines.append(
        f"- Budget: {'$' + f'{context.budget_usd:,.0f}' if context.budget_usd else 'Not specified'}"
    )
    lines.append(
        f"- Duration: {str(context.duration_days) + ' days' if context.duration_days else 'Not specified'}"
    )
    lines.append(f"- Group size: {context.group_size or 1}")
    lines.append(f"- Travel style: {context.travel_style or 'Not specified'}")
    if context.interests:
        lines.append(f"- Interests: {', '.join(context.interests)}")
    return "\n".join(lines) + "\n"
