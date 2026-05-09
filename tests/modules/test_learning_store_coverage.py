"""Ramas finas de MatchingLearningStore (historial, snapshots)."""

from __future__ import annotations

from app.ml.learning_store import MatchingLearningStore


def test_record_success_skips_unknown_dimensions():
    store = MatchingLearningStore()
    store.record_success({"unknown_dim": 0.9, "interests": 0.8})


def test_record_incompatible_low_vs_high_scores():
    store = MatchingLearningStore()
    store.record_incompatible({"interests": 0.4})
    store.record_incompatible({"interests": 0.8})


def test_outcomes_history_trimmed_after_many_events():
    store = MatchingLearningStore()
    store.outcomes = [
        {"kind": "success", "dimensions": {}, "notes": None, "weights_after": {}, "at": "x"}
        for _ in range(501)
    ]
    store.record_success({"interests": 0.5})
    assert len(store.outcomes) == 500
