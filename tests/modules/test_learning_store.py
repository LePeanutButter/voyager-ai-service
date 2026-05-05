import pytest

from app.ml.learning_store import MatchingLearningStore


def test_record_success_and_incompatible():
    store = MatchingLearningStore()
    w1 = store.record_success({"interests": 0.9})
    assert sum(w1.values()) == pytest.approx(1.0, rel=1e-2)

    w2 = store.record_incompatible({"interests": 0.95})
    assert "interests" in w2


def test_record_rating_feedback():
    store = MatchingLearningStore()
    before = store.get_weights().copy()
    store.record_rating_feedback(5)
    after = store.get_weights()
    assert after != before


def test_recent_outcomes_trim():
    store = MatchingLearningStore()
    for _ in range(3):
        store.record_success({"interests": 0.5})
    assert len(store.recent_outcomes(2)) <= 2

