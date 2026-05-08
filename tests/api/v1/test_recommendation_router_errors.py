"""Exercise error branches in local AI recommendations router."""

from fastapi.testclient import TestClient

from app.main import app


class _BoomRecommendationService:
    def recommend(self, *a, **k):
        raise RuntimeError("boom")

    def record_feedback(self, *a, **k):
        raise RuntimeError("boom")


def test_local_recommendations_500():
    with TestClient(app) as client:
        app.state.real_recommendation_service = _BoomRecommendationService()
        r = client.post(
            "/api/v1/local/recommendations",
            json={
                "user_id": "u1",
                "query": "cafe en madrid",
                "limit": 3,
                "candidates": [
                    {
                        "id": "a1",
                        "name": "Museo del Prado",
                        "category": "cultural",
                        "price": 18,
                        "content_text": "arte clasico",
                    }
                ],
            },
        )
        assert r.status_code == 500


def test_local_recommendations_feedback_500():
    with TestClient(app) as client:
        app.state.real_recommendation_service = _BoomRecommendationService()
        r = client.post(
            "/api/v1/local/recommendations/feedback",
            params={"user_id": "u1", "item_id": "a1", "rating": 5},
        )
        assert r.status_code == 500

