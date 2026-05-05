import pytest

from app.modules.behavior.schemas import BehaviorAnalysisRequest, BehaviorTrackingRequest
from app.modules.behavior.service import BehaviorAnalysisService
from app.modules.common.schemas.enums import InteractionType


@pytest.fixture
def svc():
    return BehaviorAnalysisService(model_manager=None)


@pytest.mark.asyncio
async def test_track_interaction(svc: BehaviorAnalysisService):
    ok = await svc.track_interaction(
        BehaviorTrackingRequest(
            user_id="u1",
            interaction_type=InteractionType.VIEW,
            activity_category="cultural",
        )
    )
    assert ok is True


@pytest.mark.asyncio
async def test_analyze_insufficient_data_returns_empty(svc: BehaviorAnalysisService):
    await svc.track_interaction(
        BehaviorTrackingRequest(
            user_id="u2",
            interaction_type=InteractionType.CLICK,
        )
    )
    out = svc.analyze_behavior(BehaviorAnalysisRequest(user_id="u2", analysis_period_days=7))
    assert out.confidence_score == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_analyze_tracks_rejections(svc: BehaviorAnalysisService):
    uid = "u-reject"
    for _ in range(4):
        await svc.track_interaction(
            BehaviorTrackingRequest(
                user_id=uid,
                interaction_type=InteractionType.REJECT,
                activity_category="nightlife",
            )
        )
    for _ in range(5):
        await svc.track_interaction(
            BehaviorTrackingRequest(
                user_id=uid,
                interaction_type=InteractionType.CLICK,
                activity_category="cultural",
            )
        )
    out = svc.analyze_behavior(BehaviorAnalysisRequest(user_id=uid, analysis_period_days=30))
    assert out.user_id == uid
    assert out.confidence_score >= 0.0

