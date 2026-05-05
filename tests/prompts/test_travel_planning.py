"""Tests for app.prompts.travel_planning."""

import pytest

from app.modules.chat.schemas import TravelContext
from app.prompts import travel_planning as tp


def test_render_planning_prompt_full_context():
    ctx = TravelContext(
        destination="Tokyo",
        budget_usd=1200.0,
        duration_days=5,
        group_size=2,
        travel_style="cultural",
        interests=["museums", "food"],
    )
    out = tp.render_planning_prompt("Need ideas", ctx, history_summary=None)
    assert "Tokyo" in out
    assert "Need ideas" in out
    assert "$1,200" in out  # formatted budget
    assert "5 days" in out
    assert "museums" in out


def test_render_planning_prompt_with_history():
    ctx = TravelContext()
    out = tp.render_planning_prompt("Hi", ctx, history_summary="We discussed Paris.")
    assert "Conversation So Far" in out
    assert "Paris" in out


@pytest.mark.parametrize(
    "budget_usd, duration_days, interests",
    [
        (None, None, []),
        (500.0, 3, []),
        (None, 7, ["hiking"]),
    ],
)
def test_render_context_block_variants(budget_usd, duration_days, interests):
    ctx = TravelContext(
        destination=None,
        budget_usd=budget_usd,
        duration_days=duration_days,
        interests=interests,
    )
    block = tp._render_context_block(ctx)
    assert "Current Trip Context" in block
    assert "Not specified" in block or "$" in block or "days" in block


def test_system_prompt_constant_exists():
    assert "Voyager" in tp.SYSTEM_PROMPT
