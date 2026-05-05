import pytest

from app.modules.adaptive_ui.service import AdaptiveUIService
from app.modules.behavior.service import BehaviorAnalysisService


@pytest.fixture
def adaptive():
    beh = BehaviorAnalysisService(None)
    return AdaptiveUIService(beh)


def test_menu_default_without_signals(adaptive: AdaptiveUIService):
    out = adaptive.build_menu_adaptation("new-user")
    assert out.primary_items


def test_home_feed_default(adaptive: AdaptiveUIService):
    out = adaptive.build_home_feed_layout("feed-user")
    assert out.primary_theme


@pytest.mark.asyncio
async def test_menu_with_nav_signals(adaptive: AdaptiveUIService):
    from app.modules.behavior.schemas import BehaviorTrackingRequest
    from app.modules.common.schemas.enums import InteractionType

    svc = adaptive._behavior  # noqa: SLF001
    await svc.track_interaction(
        BehaviorTrackingRequest(
            user_id="nav-u",
            interaction_type=InteractionType.CLICK,
            context={"nav_item_id": "matching"},
        )
    )
    out = adaptive.build_menu_adaptation("nav-u")
    ids = [i.nav_item_id for i in out.primary_items + out.secondary_items]
    assert "matching" in ids
