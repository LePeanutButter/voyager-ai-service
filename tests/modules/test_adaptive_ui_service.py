import pytest

from app.modules.adaptive_ui.service import AdaptiveUIService
from app.modules.behavior.service import BehaviorAnalysisService
from app.modules.behavior.schemas import BehaviorTrackingRequest
from app.modules.common.schemas.enums import InteractionType


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


@pytest.mark.asyncio
async def test_menu_secondary_when_no_usage_for_item(adaptive: AdaptiveUIService):
    svc = adaptive._behavior  # noqa: SLF001
    for _ in range(2):
        await svc.track_interaction(
            BehaviorTrackingRequest(
                user_id="u-sec",
                interaction_type=InteractionType.CLICK,
                context={"nav_item_id": "discover"},
            )
        )
    out = adaptive.build_menu_adaptation("u-sec")
    by_id = {i.nav_item_id: i for i in out.primary_items + out.secondary_items}
    assert by_id["discover"].tier.value == "primary"
    assert by_id["home"].tier.value == "secondary"


@pytest.mark.asyncio
async def test_home_feed_applies_cultural_boost(adaptive: AdaptiveUIService):
    svc = adaptive._behavior  # noqa: SLF001
    for _ in range(4):
        await svc.track_interaction(
            BehaviorTrackingRequest(
                user_id="u-feed",
                interaction_type=InteractionType.BOOKMARK,
                activity_category="cultural",
                context={"theme": "cultural"},
            )
        )

    out = adaptive.build_home_feed_layout("u-feed")
    assert out.primary_theme == "cultural"
    assert "Refuerzo aplicado a experiencias culturales" in out.feed_refresh_note
    assert out.recommendation_theme_weights["cultural"] >= 0.35
