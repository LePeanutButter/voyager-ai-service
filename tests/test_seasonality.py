"""Tests for seasonality service with explicit ingested profiles."""

from app.core.config import settings
from app.modules.seasonality.service import SeasonalityService, _coefficient_of_variation


def _svc() -> SeasonalityService:
    svc = SeasonalityService()
    svc.ingest_profiles(
        [
            {
                "destination_id": "dst_barcelona",
                "name": "Barcelona",
                "country": "Spain",
                "monthly_indices": [0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.3, 1.2, 1.0, 0.9, 0.8],
            },
            {
                "destination_id": "dst_lisbon",
                "name": "Lisbon",
                "country": "Portugal",
                "monthly_indices": [0.7, 0.8, 0.9, 1.0, 1.0, 1.1, 1.2, 1.2, 1.1, 1.0, 0.9, 0.8],
            },
        ]
    )
    return svc


def test_coefficient_of_variation_edge_cases():
    assert _coefficient_of_variation([]) == 0.0
    assert _coefficient_of_variation([0.0, 0.0, 0.0]) == 0.0
    assert _coefficient_of_variation([1.0, 2.0, 3.0]) > 0


def test_profile_and_overview():
    svc = _svc()
    p = svc.profile("dst_lisbon")
    assert p is not None
    ov = svc.overview(reference_month=5)
    assert ov.reference_month == 5
    assert len(ov.destinations) == 2


def test_visibility_multiplier_within_bounds():
    svc = _svc()
    for month in range(1, 13):
        _idx, _phase, mult = svc.visibility_multiplier("dst_barcelona", month)
        assert settings.SEASONALITY_MULT_MIN <= mult <= settings.SEASONALITY_MULT_MAX


def test_forecast_returns_points():
    svc = _svc()
    resp = svc.forecast_naive_seasonal("dst_lisbon", start_month=3, horizon_months=4)
    assert len(resp.points) == 4

