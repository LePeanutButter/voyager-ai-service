"""Tests for seasonality indices and mitigation multipliers."""

from app.core.config import settings
from app.modules.seasonality.service import SeasonalityService, _coefficient_of_variation


def test_coefficient_of_variation_edge_cases():
    assert _coefficient_of_variation([]) == 0.0
    assert _coefficient_of_variation([0.0, 0.0, 0.0]) == 0.0
    assert _coefficient_of_variation([1.0, 2.0, 3.0]) > 0


def test_profile_and_overview():
    svc = SeasonalityService()
    p = svc.profile("dst_slovenia")
    assert p is not None
    assert p.destination_id == "dst_slovenia"
    assert len(p.monthly_indices) == 12
    ov = svc.overview(reference_month=5)
    assert ov.reference_month == 5
    assert len(ov.destinations) >= 10


def test_visibility_adjustments_phases():
    svc = SeasonalityService()
    resp = svc.visibility_adjustments(
        ["dst_barcelona", "dst_maldives"],
        travel_month=6,
        apply_mitigation=True,
    )
    assert len(resp.rows) == 2
    off = svc.visibility_adjustments(["dst_barcelona"], travel_month=1, apply_mitigation=False)
    assert off.rows[0].visibility_multiplier == 1.0


def test_classify_phase_edges():
    svc = SeasonalityService()
    assert svc.classify_phase(2.0) == "peak"
    assert svc.classify_phase(0.1) == "off_peak"


def test_visibility_multiplier_within_bounds():
    svc = SeasonalityService()
    for month in range(1, 13):
        _idx, _phase, mult = svc.visibility_multiplier("dst_barcelona", month)
        assert settings.SEASONALITY_MULT_MIN <= mult <= settings.SEASONALITY_MULT_MAX


def test_unknown_destination_neutral():
    svc = SeasonalityService()
    assert svc.demand_index("dst_unknown", 6) == 1.0
    idx, phase, mult = svc.visibility_multiplier("dst_unknown", 6)
    assert idx == 1.0
    assert phase == "shoulder"
    assert mult == 1.0


def test_forecast_returns_points():
    svc = SeasonalityService()
    resp = svc.forecast_naive_seasonal("dst_lisbon", start_month=3, horizon_months=4)
    assert len(resp.points) == 4
    assert resp.points[0].month == 4


def test_visibility_peak_recommendation_text():
    svc = SeasonalityService()
    peak_month = None
    for m in range(1, 13):
        if svc.classify_phase(svc.demand_index("dst_barcelona", m)) == "peak":
            peak_month = m
            break
    assert peak_month is not None
    rows = svc.visibility_adjustments(["dst_barcelona"], peak_month, True).rows
    assert "Moderar promoción" in rows[0].recommendation
