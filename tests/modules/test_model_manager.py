import pickle

import pytest

from app.core.config import settings
from app.ml.model_loader import BaseModel, ModelManager, RecommendationModel


class _Predictor:
    def predict(self, data):
        return {"echo": data}


def _write_artifact(path):
    with open(path, "wb") as f:
        pickle.dump(_Predictor(), f)


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

