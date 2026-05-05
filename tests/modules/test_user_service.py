import pytest
from unittest.mock import MagicMock

from app.modules.users.schemas import (
    UserInteraction,
    UserPreferences,
    UserProfile,
    UserProfileUpdate,
)
from app.modules.common.schemas.enums import TravelPreference
from app.modules.users.service import UserService


@pytest.fixture
def svc():
    return UserService(MagicMock(is_ready=MagicMock(return_value=True)))


@pytest.mark.asyncio
async def test_profile_crud(svc: UserService):
    p = UserProfile(
        user_id="us1",
        name="N",
        email="e@e.com",
        preferences=UserPreferences(
            preferences=[TravelPreference.CULTURAL],
        ),
    )
    created = svc.create_user_profile(p)
    assert created.user_id == "us1"

    got = svc.get_user_profile("us1")
    assert got is not None

    upd = svc.update_user_profile("us1", UserProfileUpdate(location="Lima"))
    assert upd.location == "Lima"

    inter = UserInteraction(user_id="us1", activity_id="a1", interaction_type="view")
    svc.record_interaction(inter)
    hist = svc.get_interaction_history("us1", 10)
    assert len(hist) >= 1

    ins = svc.generate_user_insights("us1")
    assert ins

    assert svc.delete_user_profile("us1") is True
    assert svc.get_user_profile("us1") is None
