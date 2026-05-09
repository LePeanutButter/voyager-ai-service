"""Ramas adicionales y helpers de matching para cobertura (PBI matching)."""

from __future__ import annotations

import asyncio

import pytest

from app.ml.learning_store import MatchingLearningStore
from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import ConnectionOutcome, TravelPreference
from app.modules.matching.schemas import TravelerMatchRequest
from app.modules.matching.service import (
    MatchingService,
    _as_str_list,
    _norm_dest,
    _profile_destinations,
    _seeker_destinations,
    _shared_destination_labels,
)


class _FakeModelManager:
    def __init__(self, loaded=None):
        self._loaded = loaded

    def get_model(self, name: str):
        return self._loaded


class _LoadedPredictModel:
    model_name = "traveler_matching_model"
    is_loaded = True

    async def predict(self, data):
        await asyncio.sleep(0)
        return {"compatibility_score": 0.85}


class _LoadedPredictModelRaises:
    model_name = "traveler_matching_model"
    is_loaded = True

    async def predict(self, data):
        await asyncio.sleep(0)
        raise RuntimeError("predict failure")


def test_norm_dest_and_as_str_list_variants():
    assert _norm_dest(None) == ""
    assert _norm_dest("  Paris ") == "paris"
    assert _as_str_list(None) == []
    assert _as_str_list("a, b") == ["a", "b"]
    assert _as_str_list([" x ", 3]) == ["x", "3"]
    assert _as_str_list(123) == []


def test_profile_seeker_and_shared_destination_helpers():
    prof = {
        "travel_footprint": "Paris, lisbon",
        "location": " Barcelona ",
    }
    dests = _profile_destinations(prof)
    assert "paris" in dests and "barcelona" in dests

    seek = _seeker_destinations(prof, "Kyoto", ["tokyo", ""])
    assert "kyoto" in seek and "tokyo" in seek

    overlap = {"paris", "barcelona"}
    labels = _shared_destination_labels(prof, overlap)
    assert any("Paris" in x or x.startswith("P") for x in labels) or "Paris" in labels


@pytest.fixture
def svc_extra():
    store = MatchingLearningStore()
    service = MatchingService(_FakeModelManager(), store)
    service.ingest_profiles(
        [
            {
                "user_id": "seeker",
                "name": "Seeker",
                "location": "Barcelona",
                "preferences": [TravelPreference.CULTURAL],
                "travel_footprint": ["Barcelona", "Paris"],
                "travel_style": "mid-range",
                "budget_tier": "mid",
                "pace": "moderate",
                "personality_tags": ["social"],
                "age": 30,
            },
            {
                "user_id": "buddy",
                "name": "Buddy",
                "location": "Barcelona",
                "preferences": [TravelPreference.CULTURAL, TravelPreference.FOODIE],
                "travel_footprint": ["Barcelona"],
                "travel_style": "mid-range",
                "budget_tier": "mid",
                "pace": "moderate",
                "personality_tags": ["social"],
                "age": 32,
            },
            {"user_id": "", "name": "Skip"},
        ]
    )
    return service


def test_ingest_profiles_skips_blank_user_id(svc_extra: MatchingService):
    assert svc_extra.user_profiles.get("") is None


def test_find_travel_partners_missing_user_raises(svc_extra: MatchingService):
    req = TravelerMatchRequest(
        user_id="unknown",
        location=Location(latitude=41.0, longitude=2.0, city="BCN"),
        preferences=[TravelPreference.CULTURAL],
        max_matches=3,
    )
    with pytest.raises(ValueError, match="not found"):
        svc_extra.find_travel_partners(req)


@pytest.mark.asyncio
async def test_calculate_compatibility_missing_profile_returns_none(svc_extra: MatchingService):
    assert await svc_extra.calculate_compatibility("seeker", "nope") is None


@pytest.mark.asyncio
async def test_calculate_compatibility_with_ml_model(svc_extra: MatchingService):
    svc_extra.model_manager = _FakeModelManager(_LoadedPredictModel())
    out = await svc_extra.calculate_compatibility("seeker", "buddy")
    assert out is not None
    assert out["target_user_id"] == "buddy"


@pytest.mark.asyncio
async def test_matching_model_signal_fallback_on_predict_error(svc_extra: MatchingService):
    svc_extra.model_manager = _FakeModelManager(_LoadedPredictModelRaises())
    out = await svc_extra.calculate_compatibility("seeker", "buddy")
    assert out is not None


def test_preference_overlap_boost_in_find(svc_extra: MatchingService):
    req = TravelerMatchRequest(
        user_id="seeker",
        location=Location(latitude=41.39, longitude=2.15, city="Barcelona"),
        preferences=[TravelPreference.CULTURAL, TravelPreference.FOODIE],
        max_matches=5,
    )
    resp = svc_extra.find_travel_partners(req)
    assert resp.total_matches >= 1


def test_get_user_connections_status_filter(svc_extra: MatchingService):
    c = svc_extra.initiate_connection("seeker", "buddy")
    pending = svc_extra.get_user_connections("seeker", status="pending")
    assert any(x["connection_id"] == c["connection_id"] for x in pending)
    empty = svc_extra.get_user_connections("seeker", status="accepted")
    assert all(x["status"] == "accepted" for x in empty) or len(empty) == 0


def test_respond_to_unknown_connection_returns_none(svc_extra: MatchingService):
    assert svc_extra.respond_to_connection("conn_missing", "accepted") is None


def test_get_travel_buddy_recommendations_overlap(svc_extra: MatchingService):
    buddies = svc_extra.get_travel_buddy_recommendations(
        "seeker",
        focus_destination="Barcelona",
        limit=5,
        seeker_footprint=["Paris"],
    )
    assert isinstance(buddies, list)
    assert any(m.user_id == "buddy" for m in buddies)


def test_record_match_feedback(svc_extra: MatchingService):
    svc_extra.record_match_feedback("seeker", "buddy", 5, feedback_text="great")


def test_process_connection_outcome_success_and_incompatible(svc_extra: MatchingService):
    w1 = svc_extra.process_connection_outcome(
        "seeker", "buddy", ConnectionOutcome.SUCCESS, notes="ok"
    )
    assert isinstance(w1, dict) and w1
    w2 = svc_extra.process_connection_outcome(
        "seeker", "buddy", ConnectionOutcome.INCOMPATIBLE, dimension_snapshot={"interests": 0.9}
    )
    assert isinstance(w2, dict)


def test_demographic_and_multidimensional_edges(svc_extra: MatchingService):
    demo = svc_extra._calculate_demographic_compatibility({"age": 20}, {"age": 40})
    assert demo["score"] == pytest.approx(0.1)
    expl = svc_extra._generate_multidimensional_explanation(
        {"interests": 0.1, "travel_style": 0.1},
        {"interests": 0.2, "travel_style": 0.2},
    )
    assert "moderada" in expl or "Compatibilidad" in expl
    pref_empty = svc_extra._calculate_preference_compatibility([], [TravelPreference.CULTURAL])
    assert pref_empty["score"] == pytest.approx(0.0)


def test_load_profile_from_db_when_not_in_cache(svc_extra: MatchingService):
    svc_extra.user_profiles.clear()
    p = svc_extra._get_user_profile("seeker")
    assert p is not None and p["user_id"] == "seeker"


def test_get_candidate_travelers_requires_location_when_set(svc_extra: MatchingService):
    req = TravelerMatchRequest(
        user_id="seeker",
        location=Location(latitude=41.0, longitude=2.0, city="BCN"),
        max_matches=10,
    )
    cands = svc_extra._get_candidate_travelers(req)
    assert all(c.get("location") for c in cands)
