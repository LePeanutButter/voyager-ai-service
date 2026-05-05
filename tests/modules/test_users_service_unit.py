"""Unit tests for UserService."""

import pytest

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
    created = await svc.create_user_profile(p)
    assert created.user_id == "usr_unit_1"

    got = await svc.get_user_profile("usr_unit_1")
    assert got is not None

    upd = UserProfileUpdate(location="Berlin")
    updated = await svc.update_user_profile("usr_unit_1", upd)
    assert updated and updated.location == "Berlin"

    ok = await svc.delete_user_profile("usr_unit_1")
    assert ok is True


@pytest.mark.asyncio
async def test_create_duplicate_raises(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="dup", name="A", email="a@b.c", preferences=prefs)
    await svc.create_user_profile(p)
    with pytest.raises(ValueError, match="already exists"):
        await svc.create_user_profile(p)


@pytest.mark.asyncio
async def test_create_bad_email(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="bad", name="A", email="not-an-email", preferences=prefs)
    with pytest.raises(ValueError, match="Invalid email"):
        await svc.create_user_profile(p)


@pytest.mark.asyncio
async def test_update_missing_returns_none(svc):
    upd = UserProfileUpdate(location="X")
    assert await svc.update_user_profile("missing", upd) is None


@pytest.mark.asyncio
async def test_update_preferences(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="pref_u", name="A", email="a@b.c", preferences=prefs)
    await svc.create_user_profile(p)
    ok = await svc.update_user_preferences(
        "pref_u",
        UserPreferences(preferences=[TravelPreference.ADVENTURE]),
    )
    assert ok is True


@pytest.mark.asyncio
async def test_record_and_history_interactions(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="int_u", name="A", email="a@b.c", preferences=prefs)
    await svc.create_user_profile(p)

    await svc.record_interaction(
        UserInteraction(user_id="int_u", activity_id="act1", interaction_type="like")
    )
    hist = await svc.get_interaction_history("int_u", 10)
    assert len(hist) == 1


@pytest.mark.asyncio
async def test_generate_insights(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="ins_u", name="A", email="a@b.c", preferences=prefs)
    await svc.create_user_profile(p)
    await svc.record_interaction(
        UserInteraction(user_id="ins_u", activity_id="a", interaction_type="like")
    )
    insights = await svc.generate_user_insights("ins_u")
    assert insights and insights["user_id"] == "ins_u"


@pytest.mark.asyncio
async def test_generate_insights_missing_user(svc):
    assert await svc.generate_user_insights("nobody") is None


@pytest.mark.asyncio
async def test_interaction_history_limit(svc):
    prefs = UserPreferences()
    p = UserProfile(user_id="lim_u", name="A", email="a@b.c", preferences=prefs)
    await svc.create_user_profile(p)
    for i in range(3):
        await svc.record_interaction(
            UserInteraction(user_id="lim_u", activity_id=str(i), interaction_type="view")
        )
    assert len(await svc.get_interaction_history("lim_u", 2)) == 2
