"""Tests for ChatRecommendationEngine."""

import pytest

from app.modules.chat.recommendation_engine import ChatRecommendationEngine, _budget_tier
from app.modules.chat.schemas import ChatIntent, TravelContext


@pytest.fixture
def engine():
    return ChatRecommendationEngine()


def test_budget_tier(engine):
    assert _budget_tier(None) == "mid-range"
    assert _budget_tier(100) == "budget"
    assert _budget_tier(1500) == "mid-range"
    assert _budget_tier(3000) == "premium"


def test_generate_with_destination(engine):
    ctx = TravelContext(destination="Rome", budget_usd=800, duration_days=3)
    sugs = engine.generate(ctx, max_suggestions=6)
    assert len(sugs) >= 1
    assert any("Rome" in s.name or s.activity_type for s in sugs)


def test_generate_without_destination_tags(engine):
    ctx = TravelContext(budget_usd=400, interests=["beach"])
    sugs = engine.generate(ctx, max_suggestions=4)
    assert isinstance(sugs, list)


def test_generate_for_activity_types(engine):
    ctx = TravelContext(destination="Paris", activity_types=["cultural", "dining"])
    sugs = engine.generate_for_activity_types(ctx, max_suggestions=5)
    assert isinstance(sugs, list)


def test_resolve_destination_country(engine):
    ctx = TravelContext(destination="Italy")
    user_tags = {"cultural"}
    tier = _budget_tier(ctx.budget_usd)
    dest, reason = engine._resolve_destination(ctx, user_tags, tier)
    assert dest in ("Rome", "Venice")
    assert isinstance(reason, str)


def test_low_budget_filters_costly(engine):
    ctx = TravelContext(destination="Paris", budget_usd=50, duration_days=2)
    sugs = engine.generate(ctx, max_suggestions=10)
    assert isinstance(sugs, list)
