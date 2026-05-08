import pytest

from app.recommendations.services.recommendation_service import RealRecommendationService


def test_recommend_returns_ranked_items(monkeypatch):
    svc = RealRecommendationService()

    monkeypatch.setattr(svc.repo, "get_user_profile", lambda _uid: {"id": "u1", "name": "Ana", "segment": "travel"})
    monkeypatch.setattr(svc.repo, "get_user_preferences", lambda _uid: ["cultural"])
    monkeypatch.setattr(svc.repo, "get_recent_interactions", lambda _uid, limit=25: [{"item_id": "a1"}])
    monkeypatch.setattr(
        svc.repo,
        "rank_items",
        lambda query_text, candidates, limit: [
            {"id": "a1", "name": "Museo", "category": "cultural", "price": 20, "similarity": 0.72},
            {"id": "a2", "name": "Parque", "category": "nature", "price": 0, "similarity": 0.70},
        ],
    )

    out = svc.recommend(
        user_id="u1",
        query_text="arte en madrid",
        limit=2,
        candidates=[
            {"id": "a1", "name": "Museo", "category": "cultural", "price": 20, "content_text": "arte"},
            {"id": "a2", "name": "Parque", "category": "nature", "price": 0, "content_text": "outdoor"},
        ],
    )

    assert out["user"]["id"] == "u1"
    assert out["preferences"] == ["cultural"]
    assert len(out["items"]) == 2
    assert out["items"][0]["id"] == "a1"
    assert out["items"][0]["score"] >= out["items"][1]["score"]


def test_record_feedback_normalizes_rating(monkeypatch):
    svc = RealRecommendationService()
    captured = {}

    def _capture(user_id, item_id, rating):
        captured["user_id"] = user_id
        captured["item_id"] = item_id
        captured["rating"] = rating

    monkeypatch.setattr(svc.repo, "track_recommendation_feedback", _capture)
    svc.record_feedback(user_id="u1", item_id="a1", rating=10)

    assert captured["user_id"] == "u1"
    assert captured["item_id"] == "a1"
    assert captured["rating"] == pytest.approx(1.0)


def test_rerank_applies_preference_boost():
    svc = RealRecommendationService()
    items = [
        {"id": "x", "category": "nature", "similarity": 0.80},
        {"id": "y", "category": "cultural", "similarity": 0.75},
    ]
    out = svc._rerank_with_preferences(items, ["cultural"])
    assert out[0]["id"] == "y"
    assert out[0]["score"] == pytest.approx(0.83)

