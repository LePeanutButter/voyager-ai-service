import pytest
from unittest.mock import MagicMock

from app.modules.common.schemas.enums import WeatherCondition
from app.modules.recommendations.schemas import (
    ContextualActivityRequest,
    DestinationRecommendationRequest,
    RecommendationRequest,
)
from app.modules.recommendations.service import RecommendationService
from app.modules.trends.service import TrendsService


@pytest.fixture
def mock_mm():
    mm = MagicMock()
    mm.is_ready.return_value = True
    return mm


@pytest.fixture
def rec_svc(mock_mm):
    return RecommendationService(mock_mm, trends_service=None)


@pytest.mark.asyncio
async def test_get_personalized_destinations(rec_svc: RecommendationService):
    req = DestinationRecommendationRequest(
        user_id="u1",
        max_results=4,
        include_emerging_trends=False,
    )
    out = rec_svc.get_personalized_destinations(req)
    assert out.destinations


@pytest.mark.asyncio
async def test_get_personalized_destinations_with_trends(mock_mm):
    ts = TrendsService()
    await ts.refresh()
    svc = RecommendationService(mock_mm, trends_service=ts)
    req = DestinationRecommendationRequest(user_id="u1", max_results=6, include_emerging_trends=True)
    out = svc.get_personalized_destinations(req)
    assert out.destinations


@pytest.mark.asyncio
async def test_contextual_activities(rec_svc: RecommendationService):
    req = ContextualActivityRequest(
        user_id="u1",
        latitude=41.0,
        longitude=2.0,
        weather=WeatherCondition.RAIN,
        max_results=4,
    )
    out = rec_svc.get_contextual_activities(req)
    assert out.activities


@pytest.mark.asyncio
async def test_generate_recommendations(rec_svc: RecommendationService):
    from app.modules.common.schemas.base import Location

    req = RecommendationRequest(
        user_id="u1",
        location=Location(latitude=10, longitude=20, city="X"),
        max_results=3,
    )
    out = rec_svc.generate_recommendations(req)
    assert out.recommendations


@pytest.mark.asyncio
async def test_get_categories_and_trending(rec_svc: RecommendationService):
    cats = rec_svc.get_activity_categories()
    assert "cultural" in cats
    t = rec_svc.get_trending_activities(None, 2)
    assert len(t) <= 2


@pytest.mark.asyncio
async def test_get_popular_activities(rec_svc: RecommendationService):
    acts = rec_svc.get_popular_activities("Barcelona", 5)
    assert len(acts) <= 5


@pytest.mark.asyncio
async def test_get_trending_with_category(rec_svc: RecommendationService):
    t = rec_svc.get_trending_activities("cultural", 3)
    assert isinstance(t, list)


@pytest.mark.asyncio
async def test_get_similar_no_reference(rec_svc: RecommendationService):
    sim = rec_svc.get_similar_activities("missing_id_xyz", 3)
    assert sim == []


@pytest.mark.asyncio
async def test_record_feedback(rec_svc: RecommendationService):
    rec_svc.record_feedback("u1", "act1", 4, feedback_text="nice")


@pytest.mark.asyncio
async def test_generate_raises_propagates(mock_mm, monkeypatch):
    svc = RecommendationService(mock_mm)

    def boom(*a, **k):
        raise RuntimeError("fail")

    monkeypatch.setattr(svc, "_get_user_profile", boom)
    from app.modules.common.schemas.base import Location
    from app.modules.recommendations.schemas import RecommendationRequest

    req = RecommendationRequest(
        user_id="u1",
        location=Location(latitude=1, longitude=2),
        max_results=2,
    )
    with pytest.raises(RuntimeError):
        svc.generate_recommendations(req)
