import pytest

from app.modules.trends.service import TrendsService


@pytest.fixture
def svc():
    s = TrendsService()
    s.ingest_signal_rows(
        [
            {
                "destination_id": "dst_barcelona",
                "name": "Barcelona",
                "country": "Spain",
                "tags": ["cultural", "foodie"],
                "previous": 80,
                "current": 120,
            }
        ]
    )
    s.ingest_segment_library(
        {
            "culture_seekers": {
                "segment_id": "culture_seekers",
                "label": "Culture seekers",
                "weights": {"cultural": 0.8},
                "seasonal": [{"label": "primavera", "intensity": 0.7, "months_peak": [4, 5]}],
                "budget": {"avg_daily_budget": 120, "currency": "EUR"},
                "preferences": ["cultural", "foodie"],
            }
        }
    )
    return s


@pytest.mark.asyncio
async def test_refresh_and_dashboard(svc: TrendsService):
    await svc.refresh()
    out = svc.get_dashboard()
    assert out.generated_at is not None


def test_segment_insights(svc: TrendsService):
    out = svc.get_segment_insights("culture_seekers")
    assert out.insights.segment_id == "culture_seekers"


@pytest.mark.asyncio
async def test_weekly_digest(svc: TrendsService):
    await svc.refresh()
    out = svc.get_weekly_digest()
    assert out.generated_at is not None

