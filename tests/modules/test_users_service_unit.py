"""Unit tests for UserService."""

import pytest

from app.db import database as db_database
from app.db.runtime_models import UserInteractionRecord, UserProfileRecord
from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import TravelPreference
from app.modules.users.schemas import (
    UserInteraction,
    UserPreferences,
    UserProfile,
    UserProfileUpdate,
)
from app.modules.users.service import UserService


class _FakeMM:
    pass


@pytest.fixture
def svc():
    db_database.init_db_engine()
    assert db_database.SessionLocal is not None
    with db_database.SessionLocal() as db:
        db.query(UserInteractionRecord).delete()
        db.query(UserProfileRecord).delete()
        db.commit()
    return UserService(_FakeMM())


@pytest.mark.asyncio
async def test_create_get_update_delete(svc):
    prefs = UserPreferences(preferences=[TravelPreference.CULTURAL])
    p = UserProfile(
        user_id="usr_unit_1",
        name="N",
        email="n@test.com",
        preferences=prefs,
    )
    created = svc.create_user_profile(p)
    assert created.user_id == "usr_unit_1"

    got = svc.get_user_profile("usr_unit_1")
    assert got is not None

    upd = UserProfileUpdate(location="Berlin")
    updated = svc.update_user_profile("usr_unit_1", upd)
    assert updated and updated.location == "Berlin"

    ok = svc.delete_user_profile("usr_unit_1")
    assert ok is True


@pytest.mark.asyncio
async def test_create_duplicate_raises(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="dup", name="A", email="a@b.c", preferences=prefs)
    svc.create_user_profile(p)
    with pytest.raises(ValueError, match="already exists"):
        svc.create_user_profile(p)


@pytest.mark.asyncio
async def test_create_bad_email(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="bad", name="A", email="not-an-email", preferences=prefs)
    with pytest.raises(ValueError, match="Invalid email"):
        svc.create_user_profile(p)


@pytest.mark.asyncio
async def test_update_missing_returns_none(svc):
    upd = UserProfileUpdate(location="X")
    assert svc.update_user_profile("missing", upd) is None


@pytest.mark.asyncio
async def test_update_preferences(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="pref_u", name="A", email="a@b.c", preferences=prefs)
    svc.create_user_profile(p)
    ok = svc.update_user_preferences(
        "pref_u",
        UserPreferences(preferences=[TravelPreference.ADVENTURE]),
    )
    assert ok is True


@pytest.mark.asyncio
async def test_record_and_history_interactions(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="int_u", name="A", email="a@b.c", preferences=prefs)
    svc.create_user_profile(p)

    svc.record_interaction(
        UserInteraction(user_id="int_u", activity_id="act1", interaction_type="like")
    )
    hist = svc.get_interaction_history("int_u", 10)
    assert len(hist) == 1


@pytest.mark.asyncio
async def test_generate_insights(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="ins_u", name="A", email="a@b.c", preferences=prefs)
    svc.create_user_profile(p)
    svc.record_interaction(
        UserInteraction(user_id="ins_u", activity_id="a", interaction_type="like")
    )
    insights = svc.generate_user_insights("ins_u")
    assert insights and insights["user_id"] == "ins_u"


@pytest.mark.asyncio
async def test_generate_insights_missing_user(svc):
    assert svc.generate_user_insights("nobody") is None


@pytest.mark.asyncio
async def test_update_preferences_missing_user_returns_false(svc):
    assert svc.update_user_preferences("missing-user", UserPreferences()) is False


@pytest.mark.asyncio
async def test_analyze_preferences_budget_clamping(svc):
    prefs = UserPreferences(budget_range={"min": -50, "max": -1})
    out = svc._analyze_preferences(prefs)
    assert out.budget_range["min"] == 0
    assert out.budget_range["max"] >= out.budget_range["min"]


@pytest.mark.asyncio
async def test_record_interaction_appends_preference_from_metadata(svc):
    prefs = UserPreferences(preferences=[TravelPreference.CULTURAL])
    p = UserProfile(user_id="meta_pref_u", name="A", email="meta@b.c", preferences=prefs)
    svc.create_user_profile(p)
    svc.record_interaction(
        UserInteraction(
            user_id="meta_pref_u",
            activity_id="act",
            interaction_type="click",
            metadata={"category": "foodie"},
        )
    )
    profile = svc.get_user_profile("meta_pref_u")
    assert profile is not None
    pref_vals = [getattr(x, "value", x) for x in profile.preferences.preferences]
    assert "foodie" in pref_vals


@pytest.mark.asyncio
async def test_generate_insights_categories_and_positive_types(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="ins_cat_u", name="A", email="ins_cat@b.c", preferences=prefs)
    svc.create_user_profile(p)
    svc.record_interaction(
        UserInteraction(
            user_id="ins_cat_u",
            activity_id="a1",
            interaction_type="view",
            metadata={"category": "museums"},
        )
    )
    svc.record_interaction(
        UserInteraction(user_id="ins_cat_u", activity_id="a2", interaction_type="book")
    )
    insights = svc.generate_user_insights("ins_cat_u")
    assert insights and insights["interaction_count"] >= 2
    assert insights["top_categories"]


@pytest.mark.asyncio
async def test_delete_missing_profile_returns_false(svc):
    assert svc.delete_user_profile("no_such_user_xyz") is False


@pytest.mark.asyncio
async def test_update_profile_preferences_location_and_history(svc):
    prefs = UserPreferences(preferences=[TravelPreference.NATURE])
    p = UserProfile(user_id="multi_u", name="A", email="multi@b.c", preferences=prefs)
    svc.create_user_profile(p)
    upd = UserProfileUpdate(
        preferences=UserPreferences(preferences=[TravelPreference.BEACH]),
        location="Valencia",
        travel_history=[{"destination": "X"}],
    )
    out = svc.update_user_profile("multi_u", upd)
    assert out is not None
    assert out.location == "Valencia"
    assert out.travel_history


@pytest.mark.asyncio
async def test_record_interaction_invalid_category_enum_ignored(svc):
    prefs = UserPreferences(preferences=[TravelPreference.CULTURAL])
    p = UserProfile(user_id="bad_cat_u", name="A", email="bad_cat@b.c", preferences=prefs)
    svc.create_user_profile(p)
    svc.record_interaction(
        UserInteraction(
            user_id="bad_cat_u",
            activity_id="z",
            interaction_type="click",
            metadata={"category": "___not_an_enum___"},
        )
    )


@pytest.mark.asyncio
async def test_interaction_history_limit(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="lim_u", name="A", email="a@b.c", preferences=prefs)
    svc.create_user_profile(p)
    for i in range(3):
        svc.record_interaction(
            UserInteraction(user_id="lim_u", activity_id=str(i), interaction_type="view")
        )
    assert len(svc.get_interaction_history("lim_u", 2)) == 2

