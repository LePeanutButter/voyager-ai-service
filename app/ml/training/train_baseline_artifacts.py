"""Entrena con sklearn (datos sintéticos) y guarda los tres .pkl del ModelManager.

Las clases serializadas viven en ``app.ml.picklable_wrappers`` para que pickle
las resuelva al cargar el servicio (evita ``app.main.RecommendationArtifact``).

Uso (desde `voyager-ai-service/`):

    python -m app.ml.training.train_baseline_artifacts

Opcional: ``--output DIR`` (por defecto ``settings.MODEL_PATH``).
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.core.config import settings
from app.ml.picklable_wrappers import (
    RecommendationArtifact,
    TravelerMatchingArtifact,
    UserProfilingArtifact,
    matching_feature_vector,
    shallow_dict_feature_vector,
)


def _train_traveler_matching(n_samples: int = 600, seed: int = 42) -> TravelerMatchingArtifact:
    rng = np.random.default_rng(seed)
    x_list: list[np.ndarray] = []
    y_list: list[float] = []
    for _ in range(n_samples):
        size1 = int(rng.integers(1, 9))
        size2 = int(rng.integers(1, 9))
        idx1 = rng.choice(20, size=size1, replace=False)
        idx2 = rng.choice(20, size=size2, replace=False)
        prefs1 = [f"p{i}" for i in idx1]
        prefs2 = [f"p{i}" for i in idx2]
        payload = {
            "user1_profile": {"preferences": prefs1},
            "user2_profile": {"preferences": prefs2},
        }
        x_list.append(matching_feature_vector(payload))
        s1, s2 = set(prefs1), set(prefs2)
        union = len(s1 | s2)
        base = len(s1 & s2) / union if union else 0.0
        y_list.append(float(np.clip(base + rng.normal(0.0, 0.06), 0.0, 1.0)))
    x_arr = np.vstack(x_list)
    y_arr = np.array(y_list, dtype=np.float64)
    reg = RandomForestRegressor(
        n_estimators=64,
        max_depth=12,
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=-1,
    )
    reg.fit(x_arr, y_arr)
    return TravelerMatchingArtifact(reg)


def _train_recommendation(n_samples: int = 500, seed: int = 7) -> RecommendationArtifact:
    rng = np.random.default_rng(seed)
    x_list: list[np.ndarray] = []
    y_list: list[float] = []
    for _ in range(n_samples):
        d = {
            "query": f"q{rng.integers(0, 100)}",
            "context": {"budget": float(rng.random()), "tags": [f"t{i}" for i in range(int(rng.integers(0, 5)))]},
        }
        x_list.append(shallow_dict_feature_vector(d, 16))
        y_list.append(float(rng.random()))
    x_arr = np.vstack(x_list)
    y_arr = np.array(y_list, dtype=np.float64)
    reg = RandomForestRegressor(
        n_estimators=48,
        max_depth=10,
        random_state=seed,
        n_jobs=-1,
    )
    reg.fit(x_arr, y_arr)
    return RecommendationArtifact(reg)


def _train_user_profiling(n_samples: int = 500, n_classes: int = 6, seed: int = 99) -> UserProfilingArtifact:
    rng = np.random.default_rng(seed)
    x_list: list[np.ndarray] = []
    y_list: list[int] = []
    for _ in range(n_samples):
        d = {
            "preferences": [f"p{i}" for i in rng.choice(12, size=int(rng.integers(1, 6)), replace=False)],
            "meta": {"age_band": int(rng.integers(0, 4))},
        }
        x_list.append(shallow_dict_feature_vector(d, 16))
        y_list.append(int(rng.integers(0, n_classes)))
    x_arr = np.vstack(x_list)
    y_arr = np.array(y_list, dtype=np.int64)
    clf = RandomForestClassifier(
        n_estimators=48,
        max_depth=10,
        random_state=seed,
        n_jobs=-1,
    )
    clf.fit(x_arr, y_arr)
    return UserProfilingArtifact(clf)


def train_all(output_dir: Path | None = None) -> None:
    out = output_dir if output_dir is not None else Path(settings.MODEL_PATH)
    out.mkdir(parents=True, exist_ok=True)

    artifacts = [
        (settings.RECOMMENDATION_MODEL, _train_recommendation()),
        (settings.USER_PROFILING_MODEL, _train_user_profiling()),
        (settings.MATCHING_MODEL, _train_traveler_matching()),
    ]
    for filename, artifact in artifacts:
        path = out / filename
        with open(path, "wb") as f:
            pickle.dump(artifact, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"written {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline sklearn artifacts for ModelManager.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Directory for .pkl files (default: MODEL_PATH from settings)",
    )
    args = parser.parse_args()
    train_all(args.output)


if __name__ == "__main__":
    main()
