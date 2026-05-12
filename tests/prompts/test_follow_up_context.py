"""Tests for app.prompts.follow_up_context."""

from datetime import datetime, timezone

from app.modules.chat.schemas import ConversationMessage, TravelContext
from app.prompts import follow_up_context as fc


def test_render_follow_up_prompt_minimal_context():
    ctx = TravelContext()
    hist = [
        ConversationMessage(role="user", content="Hello"),
        ConversationMessage(role="assistant", content="Hi there"),
    ]
    out = fc.render_follow_up_prompt("What's next?", ctx, hist, max_history_turns=4)
    assert "Established Trip Context" in out
    assert "Recent Conversation" in out
    assert "What's next?" in out


def test_render_follow_up_prompt_full_and_truncation():
    ctx = TravelContext(
        destination="Lima",
        budget_usd=900.0,
        duration_days=10,
        travel_style="adventure",
        interests=["trekking"],
    )
    long_msg = "x" * 400
    hist = [ConversationMessage(role="user", content=long_msg)]
    out = fc.render_follow_up_prompt("More", ctx, hist, max_history_turns=1)
    assert "Lima" in out
    assert "$900" in out
    assert "..." in out  # truncated preview


def test_system_prompt_constant():
    assert "multi-turn" in fc.SYSTEM_PROMPT.lower()
