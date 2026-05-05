"""Unit tests for app.modules.matching.service.MatchingService."""

import asyncio
import pytest

from app.ml.learning_store import MatchingLearningStore
from app.modules.common.schemas.base import Location
from app.modules.common.schemas.enums import ConnectionOutcome, TravelPreference
from app.modules.matching.schemas import TravelerMatchRequest
from app.modules.matching.service import MatchingService


class _FakeModel:
    def __init__(self, loaded: bool = True, raise_on_predict: bool = False):
        self.is_loaded = loaded
        self.raise_on_predict = raise_on_predict

    async def predict(self, payload):
        await asyncio.sleep(0)
        if self.raise_on_predict:
            raise RuntimeError("model fail")
        return {"compatibility_score": 0.82}


class _FakeModelManager:
    def __init__(self, model=None):
        self._model = model

    def get_model(self, name: str):
        return self._model


@pytest.fixture
def learning_store():
    return MatchingLearningStore()


@pytest.fixture
def svc_no_ml(learning_store):
    return MatchingService(_FakeModelManager(model=None), learning_store)


@pytest.fixture
def svc_with_ml(learning_store):
    return MatchingService(_FakeModelManager(model=_FakeModel()), learning_store)


@pytest.mark.asyncio
async def test_find_travel_partners_happy_path(svc_no_ml):
    loc = Location(latitude=40.0, longitude=-74.0, city="NYC")
    req = TravelerMatchRequest(
        user_id="user1",
        location=loc,
        preferences=[TravelPreference.CULTURAL],
        max_matches=2,
    )
    resp = svc_no_ml.find_travel_partners(req)
    assert resp.user_id == "user1"
    assert resp.total_matches <= 2


@pytest.mark.asyncio
async def test_find_travel_partners_unknown_user_raises(svc_no_ml):
    loc = Location(latitude=0.0, longitude=0.0)
    req = TravelerMatchRequest(user_id="unknown", location=loc)
    with pytest.raises(ValueError, match="not found"):
        svc_no_ml.find_travel_partners(req)


@pytest.mark.asyncio
async def test_calculate_compatibility_happy_path(svc_with_ml):
    out = await svc_with_ml.calculate_compatibility("user1", "user2")
    assert out is not None
    assert out["user_id"] == "user1"
    assert "overall_score" in out
    assert "dimensions" in out


@pytest.mark.asyncio
async def test_calculate_compatibility_missing_user(svc_no_ml):
    assert await svc_no_ml.calculate_compatibility("user1", "nope") is None


@pytest.mark.asyncio
async def test_connection_flow(svc_no_ml):
    c = svc_no_ml.initiate_connection("user1", "user2", message="hi")
    assert c["status"] == "pending"
    cid = c["connection_id"]
    updated = svc_no_ml.respond_to_connection(cid, "accepted", message="ok")
    assert updated["status"] == "accepted"
    conns = svc_no_ml.get_user_connections("user1", status="accepted")
    assert len(conns) == 1


@pytest.mark.asyncio
async def test_get_user_connections_filter_and_sort(svc_no_ml):
    svc_no_ml.initiate_connection("user1", "user2")
    svc_no_ml.initiate_connection("user1", "user3")
    all_c = svc_no_ml.get_user_connections("user1")
    assert len(all_c) >= 2
    pending = svc_no_ml.get_user_connections("user1", status="pending")
    assert all(x["status"] == "pending" for x in pending)


@pytest.mark.asyncio
async def test_respond_missing_returns_none(svc_no_ml):
    assert svc_no_ml.respond_to_connection("conn_x", "declined") is None


@pytest.mark.asyncio
async def test_get_travel_buddy_recommendations(svc_no_ml):
    recs = svc_no_ml.get_travel_buddy_recommendations("user1", location="San Francisco")
    assert isinstance(recs, list)


@pytest.mark.asyncio
async def test_get_travel_buddy_unknown_user(svc_no_ml):
    assert svc_no_ml.get_travel_buddy_recommendations("nope") == []


@pytest.mark.asyncio
async def test_record_match_feedback(svc_no_ml):
    svc_no_ml.record_match_feedback("user1", "user2", 4, feedback_text="great")


@pytest.mark.asyncio
async def test_process_connection_outcome_success(svc_no_ml):
    w = svc_no_ml.process_connection_outcome(
        "user1", "user2", ConnectionOutcome.SUCCESS, dimension_snapshot={"interests": 0.8}
    )
    assert isinstance(w, dict)
    assert "interests" in w or len(w) >= 1


@pytest.mark.asyncio
async def test_process_connection_outcome_incompatible(svc_no_ml):
    w = svc_no_ml.process_connection_outcome(
        "user1", "user2", ConnectionOutcome.INCOMPATIBLE, dimension_snapshot={"interests": 0.6}
    )
    assert isinstance(w, dict)


@pytest.mark.asyncio
async def test_matching_model_signal_fallback_on_error(svc_with_ml, learning_store):
    bad = _FakeModel(loaded=True, raise_on_predict=True)
    svc = MatchingService(_FakeModelManager(model=bad), learning_store)
    dims = {"interests": 0.5, "travel_style": 0.5, "budget": 0.5, "pace": 0.5, "personality": 0.5}
    sig = await svc._matching_model_signal(
        {"user_id": "user1", "preferences": []},
        {"user_id": "user2", "preferences": []},
        dims,
    )
    assert 0.0 <= sig <= 1.0


@pytest.mark.asyncio
async def test_generate_multidimensional_explanation_branches(svc_no_ml):
    low = dict.fromkeys(("interests", "travel_style", "budget", "pace", "personality"), 0.1)
    text = svc_no_ml._generate_multidimensional_explanation(low, svc_no_ml.learning_store.get_weights())
    assert "moderada" in text or "Compatibilidad" in text

    high = {"interests": 0.9, "travel_style": 0.2, "budget": 0.1, "pace": 0.1, "personality": 0.1}
    text2 = svc_no_ml._generate_multidimensional_explanation(high, svc_no_ml.learning_store.get_weights())
    assert "alineación" in text2 or "%" in text2


@pytest.mark.asyncio
async def test_preference_compatibility_empty_sets(svc_no_ml):
    out = svc_no_ml._calculate_preference_compatibility([], [TravelPreference.CULTURAL])
    assert out["score"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_demographic_age_branches(svc_no_ml):
    u1 = {"age": 30}
    u2 = {"age": 32}
    d = svc_no_ml._calculate_demographic_compatibility(u1, u2)
    assert d["score"] == pytest.approx(1.0)

    d2 = svc_no_ml._calculate_demographic_compatibility({"age": 20}, {"age": 40})
    assert d2["score"] <= 0.7
