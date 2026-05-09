import os
import pickle

import pytest

from app.core.config import settings
from app.ml.model_loader import (
    BaseModel,
    ModelManager,
    RecommendationModel,
    UserProfilingModel,
    TravelerMatchingModel,
)


class _Predictor:
    def predict(self, data):
        return {"echo": data}


class _CallableArtifact:
    """Pickle-friendly callable for ``BaseModel._call_predict``."""

    def __call__(self, data):
        return {"compatibility_score": 0.66}


class _BadPredictor:
    def predict(self, data):
        raise ValueError("boom")


def _write_artifact(path, obj=None):
    with open(path, "wb") as f:
        pickle.dump(obj if obj is not None else _Predictor(), f)


@pytest.mark.asyncio
async def test_model_manager_lifecycle(tmp_path, monkeypatch):
    _write_artifact(tmp_path / settings.RECOMMENDATION_MODEL)
    _write_artifact(tmp_path / settings.USER_PROFILING_MODEL)
    _write_artifact(tmp_path / settings.MATCHING_MODEL)
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))

    mm = ModelManager()
    ok = await mm.load_models()
    assert ok is True
    assert mm.is_ready() is True
    assert await mm.reload_model("recommendation_model") is True
    await mm.shutdown()
    assert mm.is_ready() is False


@pytest.mark.asyncio
async def test_recommendation_model_missing_file(tmp_path):
    model = RecommendationModel(str(tmp_path / "missing.pkl"))
    assert await model.load_model() is False
    with pytest.raises(RuntimeError):
        await model.predict({"x": 1})


def test_base_model_interface_exposed():
    assert BaseModel.__abstractmethods__


@pytest.mark.asyncio
async def test_base_model_call_predict_callable_artifact(tmp_path):
    path = tmp_path / "callable.pkl"
    _write_artifact(path, _CallableArtifact())
    m = RecommendationModel(str(path))
    assert await m.load_model() is True
    out = await m.predict({"healthcheck": True})
    assert out["compatibility_score"] == 0.66


@pytest.mark.asyncio
async def test_validate_model_false_when_predict_raises(tmp_path):
    path = tmp_path / "bad.pkl"
    _write_artifact(path, _BadPredictor())
    m = RecommendationModel(str(path))
    assert await m.load_model() is True
    assert await m.validate_model() is False


@pytest.mark.asyncio
async def test_validate_model_not_loaded():
    m = RecommendationModel("/nonexistent/model.pkl")
    assert await m.validate_model() is False


@pytest.mark.asyncio
async def test_model_manager_load_models_aborts_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))
    _write_artifact(tmp_path / settings.RECOMMENDATION_MODEL)
    mm = ModelManager()
    assert await mm.load_models() is False
    assert mm.is_initialized is False


@pytest.mark.asyncio
async def test_model_manager_metadata_validate_reload_unknown(tmp_path, monkeypatch):
    _write_artifact(tmp_path / settings.RECOMMENDATION_MODEL)
    _write_artifact(tmp_path / settings.USER_PROFILING_MODEL)
    _write_artifact(tmp_path / settings.MATCHING_MODEL)
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))

    mm = ModelManager()
    await mm.load_models()
    meta = mm.get_model_metadata()
    assert "recommendation_model" in meta and meta["recommendation_model"]["is_loaded"] is True
    results = await mm.validate_all_models()
    assert all(results.values())
    assert await mm.reload_model("does_not_exist") is False


@pytest.mark.asyncio
async def test_validate_all_models_exception_per_model(tmp_path, monkeypatch):
    _write_artifact(tmp_path / settings.RECOMMENDATION_MODEL)
    _write_artifact(tmp_path / settings.USER_PROFILING_MODEL)
    _write_artifact(tmp_path / settings.MATCHING_MODEL)
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))

    mm = ModelManager()
    await mm.load_models()

    async def boom(self):
        raise RuntimeError("validation boom")

    monkeypatch.setattr(RecommendationModel, "validate_model", boom)
    out = await mm.validate_all_models()
    assert out["recommendation_model"] is False


@pytest.mark.asyncio
async def test_user_profiling_and_matching_predict_guard(tmp_path):
    um = UserProfilingModel(str(tmp_path / "missing_up.pkl"))
    tm = TravelerMatchingModel(str(tmp_path / "missing_tm.pkl"))
    assert await um.load_model() is False
    assert await tm.load_model() is False
    with pytest.raises(RuntimeError):
        await um.predict({})
    with pytest.raises(RuntimeError):
        await tm.predict({})


@pytest.mark.asyncio
async def test_model_manager_load_models_outer_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "makedirs", boom)
    mm = ModelManager()
    assert await mm.load_models() is False


@pytest.mark.asyncio
async def test_reload_model_reports_failure_when_reload_returns_false(tmp_path, monkeypatch):
    _write_artifact(tmp_path / settings.RECOMMENDATION_MODEL)
    _write_artifact(tmp_path / settings.USER_PROFILING_MODEL)
    _write_artifact(tmp_path / settings.MATCHING_MODEL)
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))

    mm = ModelManager()
    await mm.load_models()

    async def fail_load(_self):
        return False

    monkeypatch.setattr(RecommendationModel, "load_model", fail_load)
    assert await mm.reload_model("recommendation_model") is False

