"""
Follow-up / multi-turn context prompt template.

Used when the user sends a follow-up message (clarification, topic change,
or continuation) and we need to inject prior conversation context to
keep the LLM grounded in the evolving trip plan.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.modules.chat.schemas import ConversationMessage, TravelContext


SYSTEM_PROMPT = """You are an expert AI travel planning assistant for the Voyager platform.
You are continuing a multi-turn conversation about trip planning.

Key behaviours:
- ALWAYS remember the established context (destination, budget, duration, style)
- Build on previous answers — do not repeat information already given
- If the user changes topic (e.g., asks about food after discussing activities), adapt naturally
- When the context evolves (new budget, different destination), acknowledge the change
- Keep replies focused and concise; avoid re-listing everything from previous turns
"""


def render_follow_up_prompt(
    user_message: str,
    context: "TravelContext",
    recent_history: List["ConversationMessage"],
    max_history_turns: int = 6,
) -> str:
    """
    Build the prompt for a follow-up / multi-turn message.

    Args:
        user_message      : The raw user message.
        context           : Current extracted travel context.
        recent_history    : Recent conversation messages (newest-last order).
        max_history_turns : Number of recent turns to include in the prompt.

    Returns:
        Formatted prompt string for the user turn.
    """
    # Summarise established context
    context_lines = ["## Established Trip Context"]
    if context.destination:
        context_lines.append(f"- Destination: {context.destination}")
    if context.budget_usd is not None:
        context_lines.append(f"- Budget: ${context.budget_usd:,.0f}")
    if context.duration_days:
        context_lines.append(f"- Duration: {context.duration_days} days")
    if context.travel_style:
        context_lines.append(f"- Style: {context.travel_style}")
    if context.interests:
        context_lines.append(f"- Interests: {', '.join(context.interests)}")
    context_block = "\n".join(context_lines)

    # Build a short conversation history excerpt
    history_turns = recent_history[-max_history_turns:]
    history_lines = ["## Recent Conversation"]
    for msg in history_turns:
        role_label = "User" if msg.role == "user" else "Assistant"
        # Truncate long messages for the prompt
        content_preview = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
        history_lines.append(f"**{role_label}:** {content_preview}")
    history_block = "\n".join(history_lines)

    return (
        f"{context_block}\n\n"
        f"{history_block}\n\n"
        f"## Latest User Message\n{user_message}\n\n"
        "Continue the conversation naturally, building on established context."
    )
