"""Envoltorios sklearn serializables con ``predict(dict)``.

Deben vivir en este módulo fijo (no en scripts de entrenamiento ni en ``app.main``)
para que ``pickle.load`` resuelva las clases al arrancar uvicorn/FastAPI.

Contrato: cada instancia expone ``predict(self, data: dict) -> dict``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor


def matching_feature_vector(data: dict) -> np.ndarray:
    """Vector fijo (8) a partir del payload de matching."""
    if data.get("healthcheck"):
        return np.zeros(8, dtype=np.float64)
    p1 = (data.get("user1_profile") or {}).get("preferences") or []
    p2 = (data.get("user2_profile") or {}).get("preferences") or []
    s1, s2 = set(p1), set(p2)
    union = len(s1 | s2)
    inter = len(s1 & s2)
    jacc = inter / union if union else 0.0
    n1, n2 = len(s1), len(s2)
    return np.array(
        [
            jacc,
            n1 / 20.0,
            n2 / 20.0,
            min(n1, n2) / max(max(n1, n2), 1),
            float(inter),
            float(union),
            float(n1 + n2) / 40.0,
            0.0,
        ],
        dtype=np.float64,
    )


def shallow_dict_feature_vector(data: dict[str, Any], max_dim: int = 16) -> np.ndarray:
    """Codifica un dict arbitrario en vector fijo."""
    if data.get("healthcheck"):
        return np.zeros(max_dim, dtype=np.float64)
    vec: list[float] = []
    for k, v in sorted(data.items())[:24]:
        if k == "healthcheck":
            continue
        vec.append((hash(k) % 997) / 997.0)
        if isinstance(v, dict):
            vec.append(min(len(v), 50) / 50.0)
            for sk, sv in list(sorted(v.items()))[:3]:
                vec.append((hash(str(sk)) % 251) / 251.0)
                vec.append(min(len(str(sv)), 200) / 200.0)
        else:
            vec.append(min(len(str(v)), 500) / 500.0)
        if len(vec) >= max_dim:
            break
    while len(vec) < max_dim:
        vec.append(0.0)
    return np.array(vec[:max_dim], dtype=np.float64)


class TravelerMatchingArtifact:
    """Regresor + ``predict`` con ``compatibility_score``."""

    __slots__ = ("_reg",)

    def __init__(self, regressor: RandomForestRegressor) -> None:
        self._reg = regressor

    def predict(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("healthcheck"):
            return {"compatibility_score": 0.75}
        x = matching_feature_vector(data).reshape(1, -1)
        score = float(self._reg.predict(x)[0])
        return {"compatibility_score": max(0.0, min(1.0, score))}


class RecommendationArtifact:
    __slots__ = ("_reg",)

    def __init__(self, reg: RandomForestRegressor) -> None:
        self._reg = reg

    def predict(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("healthcheck"):
            return {"relevance": 1.0}
        x = shallow_dict_feature_vector(data, 16).reshape(1, -1)
        rel = float(self._reg.predict(x)[0])
        return {"relevance": max(0.0, min(1.0, rel))}


class UserProfilingArtifact:
    __slots__ = ("_clf",)

    def __init__(self, clf: RandomForestClassifier) -> None:
        self._clf = clf

    def predict(self, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("healthcheck"):
            return {"segment": 0, "confidence": 1.0}
        x = shallow_dict_feature_vector(data, 16).reshape(1, -1)
        seg = int(self._clf.predict(x)[0])
        proba = self._clf.predict_proba(x)[0]
        conf = float(np.max(proba))
        return {"segment": seg, "confidence": conf}
