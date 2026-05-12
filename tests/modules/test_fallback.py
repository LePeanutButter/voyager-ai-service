from app.modules.chat.schemas import Suggestion, TravelContext
from app.integrations import fallback as fb


def test_greeting():
    assert "Hello" in fb.build_greeting_reply() or len(fb.build_greeting_reply()) > 0


def test_build_planning_reply():
    ctx = TravelContext(destination="Lisbon", budget_usd=800.0)
    sug = [
        Suggestion(
            name="Day 1: walk",
            activity_type="outdoor",
            description="stroll",
            estimated_cost_usd=0,
        )
    ]
    text = fb.build_planning_reply(ctx, sug)
    assert "Lisbon" in text or "walk" in text


def test_build_planning_reply_no_suggestions_asks_missing():
    ctx = TravelContext()
    text = fb.build_planning_reply(ctx, [])
    assert "destination" in text.lower() or "budget" in text.lower()


def test_build_planning_reply_no_suggestions_interests_only():
    ctx = TravelContext(destination="X", budget_usd=100.0, duration_days=3)
    text = fb.build_planning_reply(ctx, [])
    assert "interests" in text.lower() or "activities" in text.lower()


def test_format_destinations_empty():
    assert fb._format_destinations([]) == ""


def test_format_activities_day_groups_and_others():
    ctx = TravelContext(group_size=3)
    acts = [
        Suggestion(name="Day 1: Museum", activity_type="x", description="", estimated_cost_usd=15),
        Suggestion(name="Plain hike", activity_type="x", description="", estimated_cost_usd=0),
        Suggestion(name="Day 2: badsplit", activity_type="x", description="", estimated_cost_usd=0),
    ]
    out = fb._format_activities(acts, ctx)
    assert "Day 1" in out
    assert "Museum" in out
    assert "per person" in out
    assert "Plain hike" in out


def test_format_itinerary_mixed():
    ctx = TravelContext()
    sugg = [
        Suggestion(
            name="Paris",
            activity_type="destination",
            description="nice",
            estimated_cost_usd=0,
        ),
        Suggestion(
            name="Day 1: cafe",
            activity_type="food",
            description="",
            estimated_cost_usd=20,
        ),
    ]
    out = fb._format_itinerary(sugg, ctx)
    assert "Paris" in out
    assert "cafe" in out


def test_build_intro_string_variants():
    t1 = TravelContext(duration_days=3, budget_usd=100, destination="Rome", group_size=2)
    assert "3-day" in fb._build_intro_string(t1)
    assert "partner" in fb._build_intro_string(t1)

    t2 = TravelContext(budget_usd=3000, group_size=4, destination="NYC")
    s2 = fb._build_intro_string(t2)
    assert "premium" in s2 or "4 people" in s2

    t3 = TravelContext(travel_style="solo", group_size=1)
    assert "solo" in fb._build_intro_string(t3)


def test_build_budget_reply():
    ctx = TravelContext(budget_usd=500)
    t = fb.build_budget_reply(ctx, [], old_budget=400.0)
    assert isinstance(t, str)
    assert "500" in t

    t2 = fb.build_budget_reply(ctx, [], old_budget=None)
    assert "500" in t2

    dest = Suggestion(
        name="X", activity_type="destination", description="d", estimated_cost_usd=0
    )
    t3 = fb.build_budget_reply(ctx, [dest], old_budget=600.0)
    assert "X" in t3 or "lower" in t3.lower()


def test_build_follow_up_reply_keywords():
    ctx = TravelContext(destination="Madrid")
    s = [
        Suggestion(
            name="Tapas",
            activity_type="food",
            description="yum",
            estimated_cost_usd=0,
        )
    ]
    assert "food" in fb.build_follow_up_reply(ctx, s, "I want food").lower()
    assert "cultural" in fb.build_follow_up_reply(ctx, s, "museum and history").lower()
    assert "adventure" in fb.build_follow_up_reply(ctx, s, "hike and active").lower()

    only_ctx = TravelContext(destination="Sevilla")
    out = fb.build_follow_up_reply(only_ctx, [], "generic")
    assert "Sevilla" in out

    no_dest = TravelContext()
    out2 = fb.build_follow_up_reply(no_dest, [], "hello")
    assert "thoughts" in out2.lower() or "trip" in out2.lower()


def test_identify_missing_context():
    c = TravelContext()
    m = fb._identify_missing_context(c)
    assert "destination" in m and "budget" in m


def test_budget_tier_helper():
    assert fb._budget_tier(None) == "mid-range"
    assert fb._budget_tier(100) == "budget"
    assert fb._budget_tier(3000) == "premium"
