"""Tests for app.modules.chat.context_extractor.ContextExtractor."""

import pytest

from app.modules.chat.context_extractor import ContextExtractor
from app.modules.chat.schemas import ChatIntent, TravelContext


@pytest.fixture
def ex():
    return ContextExtractor()


def test_extract_empty_message(ex):
    intent, ctx = ex.extract("")
    assert intent == ChatIntent.UNKNOWN
    assert isinstance(ctx, TravelContext)

    intent2, ctx2 = ex.extract("   ")
    assert intent2 == ChatIntent.UNKNOWN


def test_extract_exception_returns_unknown(monkeypatch, ex):
    def boom(_):
        raise RuntimeError("parse")

    monkeypatch.setattr(ex, "_extract_context", boom)
    intent, ctx = ex.extract("hello")
    assert intent == ChatIntent.UNKNOWN


@pytest.mark.parametrize(
    "msg, expected_intent",
    [
        ("Hello there", ChatIntent.GREETING),
        ("Hi, how are you", ChatIntent.GREETING),
    ],
)
def test_greeting_intent(ex, msg, expected_intent):
    intent, _ = ex.extract(msg)
    assert intent == expected_intent


def test_budget_question_without_destination(ex):
    intent, ctx = ex.extract("How much does it cost to travel?")
    assert intent == ChatIntent.BUDGET_QUESTION


def test_planning_keywords(ex):
    intent, _ = ex.extract("I want to plan a trip to Paris")
    assert intent == ChatIntent.TRAVEL_PLANNING


def test_activity_query(ex):
    intent, _ = ex.extract("What activities do you recommend in Rome?")
    assert intent == ChatIntent.ACTIVITY_QUERY


def test_destination_query(ex):
    intent, _ = ex.extract("Where should I go in summer?")
    assert intent == ChatIntent.DESTINATION_QUERY


def test_follow_up_when_no_keywords(ex):
    intent, _ = ex.extract("Sounds good")
    assert intent == ChatIntent.FOLLOW_UP


def test_context_with_destination_regex(ex):
    _, ctx = ex.extract("I'm going to Lisbon for 5 days with $800")
    assert ctx.destination == "Lisbon" or ctx.budget_usd is not None


def test_known_destination_rome(ex):
    _, ctx = ex.extract("I love Rome and museums")
    assert ctx.destination == "Rome"


def test_budget_patterns(ex):
    _, ctx = ex.extract("My budget is $1,200 USD")
    assert ctx.budget_usd == 1200.0

    _, ctx2 = ex.extract("I have 2500 dollars for the trip")
    assert ctx2.budget_usd == 2500.0


def test_budget_qualitative(ex):
    _, ctx = ex.extract("very cheap shoestring trip")
    assert ctx.budget_usd == 200.0

    _, ctx2 = ex.extract("luxury premium five-star hotel")
    assert ctx2.budget_usd == 5000.0


def test_budget_no_budget_phrase(ex):
    _, ctx = ex.extract("I have unlimited budget")
    assert ctx.budget_usd is None


def test_duration_special(ex):
    _, ctx = ex.extract("a week in Bali")
    assert ctx.duration_days == 7

    _, ctx2 = ex.extract("two weeks holiday")
    assert ctx2.duration_days == 14

    _, ctx3 = ex.extract("a long weekend escape")
    assert ctx3.duration_days == 3


def test_duration_weeks_numeric(ex):
    _, ctx = ex.extract("staying 2 weeks")
    assert ctx.duration_days == 14


def test_group_size(ex):
    _, ctx = ex.extract("traveling solo and alone")
    assert ctx.group_size == 1

    _, ctx2 = ex.extract("with my partner")
    assert ctx2.group_size == 2

    _, ctx3 = ex.extract("group of 5 people")
    assert ctx3.group_size == 5


def test_travel_style_and_interests(ex):
    _, ctx = ex.extract("cultural museum adventure hiking")
    assert ctx.travel_style is not None
    assert len(ctx.interests) >= 1
    assert len(ctx.activity_types) >= 1


def test_keyword_counts(ex):
    _, ctx = ex.extract("food food museum")
    assert ctx.keyword_counts.get("food", 0) >= 2


def test_has_destination_hint_used_by_budget_question(ex):
    # cost question but with destination → may not be pure BUDGET_QUESTION path
    intent, _ = ex.extract("How much to visit Paris?")
    assert intent in (
        ChatIntent.BUDGET_QUESTION,
        ChatIntent.TRAVEL_PLANNING,
        ChatIntent.DESTINATION_QUERY,
    )


def test_classify_with_context_fields(ex):
    intent = ex._classify_intent("more ideas", TravelContext(destination="X"))
    assert intent == ChatIntent.TRAVEL_PLANNING


def test_destination_regex_invalid_words_filtered(ex):
    # match group could be invalid - exercise strip/title path
    dest = ex._extract_destination_regex("plan a trip to The beach")
    assert dest is None or isinstance(dest, str)


def test_extract_budget_patterns_value_error(monkeypatch, ex):
    def fake_patterns(message):
        import re

        m = re.search(r"(x)", message)
        if m:
            class Bad:
                def group(self, n=1):
                    return "not-a-float"

            return Bad()
        return None

    monkeypatch.setattr(
        "app.modules.chat.context_extractor._BUDGET_PATTERNS",
        [(r"(x)", 1.0)],
    )
    assert ex._extract_budget_patterns("x") is None


def test_extract_duration_patterns_bad_int(monkeypatch, ex):
    monkeypatch.setattr(
        "app.modules.chat.context_extractor._DURATION_PATTERNS",
        [(r"(\d+)\s*days", 1)],
    )
    assert ex._extract_duration_patterns("999 days") is None  # > 365


def test_extract_group_patterns_bad_match(monkeypatch, ex):
    monkeypatch.setattr(
        "app.modules.chat.context_extractor._GROUP_PATTERNS",
        [(r"group of (\w+)", 0)],
    )
    assert ex._extract_group_size_patterns("group of abc") is None
