"""Tests for ProactiveEngine."""

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.chat.proactive_engine import ProactiveEngine
from app.modules.chat.schemas import ConversationMessage, TravelContext


@pytest.fixture
def engine():
    return ProactiveEngine()


def test_evaluate_empty(engine):
    # group_size default 1 triggers solo-social; use 2 to keep list empty with empty history
    assert engine.evaluate(TravelContext(group_size=2), []) == []


def test_repeated_topic(engine):
    ctx = TravelContext(destination="Alps", keyword_counts={"food": 3})
    hist = [ConversationMessage(role="user", content="x")]
    out = engine.evaluate(ctx, hist)
    assert len(out) >= 1
    assert out[0].is_proactive


def test_repeated_topic_unknown_keyword(engine):
    ctx = TravelContext(group_size=2, keyword_counts={"xyzunknown": 5})
    hist = [ConversationMessage(role="user", content="a")]
    assert engine.evaluate(ctx, hist) == []


def test_soon_trip(engine):
    soon = (datetime.now(timezone.utc) + timedelta(days=3)).date().isoformat()
    ctx = TravelContext(start_date=soon)
    hist = [ConversationMessage(role="user", content="hi")]
    out = engine.evaluate(ctx, hist)
    assert any("Soon" in s.name or "Coming" in s.name for s in out)


def test_soon_trip_bad_date_skipped(engine):
    ctx = TravelContext(start_date="not-a-date")
    assert engine._check_soon_trip(ctx) is None


def test_no_budget_prompt(engine):
    ctx = TravelContext()
    hist = [ConversationMessage(role="user", content=str(i)) for i in range(4)]
    sug = engine._check_no_budget(ctx, user_message_count=4)
    assert sug is not None and sug.is_proactive


def test_no_destination_prompt(engine):
    ctx = TravelContext()
    hist = []
    sug = engine._check_no_destination(ctx, user_message_count=5)
    assert sug is not None


def test_long_trip(engine):
    ctx = TravelContext(duration_days=20)
    sug = engine._check_long_trip(ctx)
    assert sug is not None


def test_solo_social(engine):
    ctx = TravelContext(group_size=1, travel_style="solo")
    sug = engine._check_solo_social(ctx)
    assert sug is not None


def test_family_friendly(engine):
    ctx = TravelContext(group_size=5, destination="Orlando")
    sug = engine._check_family_friendly(ctx)
    assert sug is not None
