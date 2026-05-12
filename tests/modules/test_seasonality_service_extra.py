"""Ramas adicionales de SeasonalityService (validación, fases, picos)."""

from __future__ import annotations

import pytest

from app.modules.seasonality.service import SeasonalityService


@pytest.fixture
def season_empty(monkeypatch):
    monkeypatch.setattr(SeasonalityService, "_load_profiles", lambda self: None)
    return SeasonalityService()


def test_ingest_profiles_rejects_wrong_month_count(season_empty: SeasonalityService):
    with pytest.raises(ValueError, match="12"):
        season_empty.ingest_profiles(
            [
                {
                    "destination_id": "bad",
                    "name": "B",
                    "country": "C",
                    "monthly_indices": [1.0] * 11,
                }
            ]
        )


def test_demand_index_unknown_destination_raises(season_empty: SeasonalityService):
    with pytest.raises(ValueError, match="not ingested"):
        season_empty.demand_index("missing_dest", 3)


def test_visibility_multiplier_high_index_branch(season_empty: SeasonalityService):
    season_empty.ingest_profiles(
        [
            {
                "destination_id": "peaky",
                "name": "P",
                "country": "C",
                "monthly_indices": [1.35] * 12,
            }
        ]
    )
    idx, phase, _mult = season_empty.visibility_multiplier("peaky", 4)
    assert idx > 1.0
    assert phase == "peak"


def test_visibility_adjustments_shoulder_phase_copy(season_empty: SeasonalityService):
    season_empty.ingest_profiles(
        [
            {
                "destination_id": "shoulder",
                "name": "S",
                "country": "C",
                "monthly_indices": [1.0] * 12,
            }
        ]
    )
    resp = season_empty.visibility_adjustments(["shoulder"], travel_month=5, apply_mitigation=True)
    assert len(resp.rows) == 1
    assert "equilibrada" in resp.rows[0].recommendation
