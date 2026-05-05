import pytest

from app.modules.trends.service import TrendsService


@pytest.fixture
def svc():
    return TrendsService()


@pytest.mark.asyncio
async def test_refresh_and_dashboard(svc: TrendsService):
    await svc.refresh()
    d = svc.get_dashboard()
    assert d.emerging_destinations


@pytest.mark.asyncio
async def test_segment_insights_known_and_fallback(svc: TrendsService):
    await svc.ensure_initialized()
    r = svc.get_segment_insights("family_budget")
    assert r.insights.segment_id == "family_budget"
    r2 = svc.get_segment_insights("unknown_segment")
    assert r2.insights.segment_id == "family_budget"


@pytest.mark.asyncio
async def test_weekly_digest(svc: TrendsService):
    await svc.ensure_initialized()
    w = svc.get_weekly_digest()
    assert w.micro_trends or w.partner_notifications is not None


@pytest.mark.asyncio
async def test_emerging_for_preferences(svc: TrendsService):
    await svc.refresh()
    hits = svc.emerging_for_preferences({"cultural", "nature"})
    assert isinstance(hits, list)
