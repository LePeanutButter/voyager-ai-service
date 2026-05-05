"""Tests for app.prompts.budget_adjustment."""

import pytest

from app.modules.chat.schemas import TravelContext
from app.prompts import budget_adjustment as ba


@pytest.mark.parametrize(
    "old_budget, new_budget, expected_snippet",
    [
        (100.0, 400.0, "Changed from"),
        (None, 250.0, "Newly set"),
    ],
)
def test_render_budget_adjustment_prompt(old_budget, new_budget, expected_snippet):
    ctx = TravelContext(destination="Berlin", duration_days=4, group_size=1)
    text = ba.render_budget_adjustment_prompt("Updated budget", ctx, old_budget, new_budget)
    assert expected_snippet in text
    assert "Berlin" in text
    assert "Budget tier" in text


@pytest.mark.parametrize(
    "usd, tier_kw",
    [
        (100.0, "very budget"),
        (400.0, "budget ($300"),
        (750.0, "economy"),
        (1500.0, "mid-range ($1000"),
        (3000.0, "upper mid-range"),
        (6000.0, "premium"),
    ],
)
def test_budget_tier_branches(usd, tier_kw):
    assert tier_kw in ba._budget_tier(usd)


def test_system_prompt_constant():
    assert "budget" in ba.SYSTEM_PROMPT.lower()
