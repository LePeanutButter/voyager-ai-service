"""
Exercise exception branches in recommendations router (HTTP 500 paths).
"""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api.deps import get_recommendation_service
from app.main import app


class _BoomRecommendationService:
    async def get_personalized_destinations(self, *a, **k):
        raise RuntimeError("boom")

    async def get_contextual_activities(self, *a, **k):
        raise RuntimeError("boom")

    async def generate_recommendations(self, *a, **k):
        raise RuntimeError("boom")

    async def get_popular_activities(self, *a, **k):
        raise RuntimeError("boom")

    async def get_trending_activities(self, *a, **k):
        raise RuntimeError("boom")

    async def get_similar_activities(self, *a, **k):
        raise RuntimeError("boom")

    async def record_feedback(self, *a, **k):
        raise RuntimeError("boom")

    async def get_activity_categories(self, *a, **k):
        raise RuntimeError("boom")


def _override_recommendation_boom(_request: Request):
    return _BoomRecommendationService()


@pytest.fixture
def override_boom():
    app.dependency_overrides[get_recommendation_service] = _override_recommendation_boom
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_override(override_boom):
    with TestClient(app) as c:
        yield c


def test_destinations_personalized_500(client_override):
    r = client_override.post(
        "/api/v1/recommendations/destinations/personalized",
        json={"user_id": "u1", "max_results": 4},
    )
    assert r.status_code == 500


def test_contextual_activities_500(client_override):
    r = client_override.post(
        "/api/v1/recommendations/activities/contextual",
        json={
            "user_id": "u1",
            "latitude": 41.0,
            "longitude": 2.0,
            "max_results": 4,
        },
    )
    assert r.status_code == 500


def test_personalized_500(client_override):
    r = client_override.post(
        "/api/v1/recommendations/personalized",
        json={
            "user_id": "u1",
            "location": {
                "latitude": 41.39,
                "longitude": 2.15,
                "city": "Barcelona",
                "country": "Spain",
                "radius_km": 25,
            },
            "max_results": 3,
        },
    )
    assert r.status_code == 500


def test_popular_500(client_override):
    r = client_override.get("/api/v1/recommendations/popular/Barcelona")
    assert r.status_code == 500


def test_trending_500(client_override):
    r = client_override.get("/api/v1/recommendations/trending")
    assert r.status_code == 500


def test_similar_500(client_override):
    r = client_override.get("/api/v1/recommendations/similar/act1")
    assert r.status_code == 500


def test_feedback_500(client_override):
    r = client_override.post(
        "/api/v1/recommendations/feedback",
        params={"user_id": "u1", "activity_id": "a1", "rating": 3},
    )
    assert r.status_code == 500


def test_categories_500(client_override):
    r = client_override.get("/api/v1/recommendations/categories")
    assert r.status_code == 500
