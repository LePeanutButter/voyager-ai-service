import pytest

from app.ml.model_loader import (
    ModelManager,
    RecommendationModel,
    TravelerMatchingModel,
    UserProfilingModel,
)


@pytest.mark.asyncio
async def test_model_manager_lifecycle():
    mm = ModelManager()
    ok = await mm.load_models()
    assert ok is True
    assert mm.is_ready()
    meta = mm.get_model_metadata()
    assert "recommendation_model" in meta
    val = await mm.validate_all_models()
    assert isinstance(val, dict)
    rel = await mm.reload_model("recommendation_model")
    assert rel is True
    bad = await mm.reload_model("nonexistent")
    assert bad is False
    await mm.shutdown()
    assert not mm.is_ready()


@pytest.mark.asyncio
async def test_recommendation_model(tmp_path):
    m = RecommendationModel(str(tmp_path / "x.pkl"))
    assert await m.load_model() is True
    pred = await m.predict({"user_id": "a", "context": {}})
    assert "user_id" in pred
    assert await m.validate_model() in (True, False)


@pytest.mark.asyncio
async def test_user_profiling_model(tmp_path):
    m = UserProfilingModel(str(tmp_path / "u.pkl"))
    await m.load_model()
    out = await m.predict({"user_id": "u", "interactions": []})
    assert "user_id" in out


@pytest.mark.asyncio
async def test_traveler_model(tmp_path):
    m = TravelerMatchingModel(str(tmp_path / "m.pkl"))
    await m.load_model()
    out = await m.predict(
        {
            "user1_id": "a",
            "user2_id": "b",
            "user1_profile": {},
            "user2_profile": {},
        }
    )
    assert "compatibility_score" in out
