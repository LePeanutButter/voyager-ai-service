"""Smoke test: entrenamiento baseline escribe .pkl cargables por ModelManager."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.ml.model_loader import ModelManager
from app.ml.training.train_baseline_artifacts import train_all


@pytest.mark.asyncio
async def test_train_baseline_then_model_manager_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MODEL_PATH", str(tmp_path))
    train_all(tmp_path)

    mm = ModelManager()
    assert mm.model_directory == str(tmp_path)
    ok = await mm.load_models()
    assert ok is True
    assert mm.is_ready() is True

    m = mm.get_model("traveler_matching_model")
    assert m is not None
    out = await m.predict({"healthcheck": True})
    assert "compatibility_score" in out
