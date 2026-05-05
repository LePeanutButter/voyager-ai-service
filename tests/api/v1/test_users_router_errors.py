"""HTTP 500 branches for users router via dependency override."""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api.deps import get_user_service
from app.main import app


class _BoomUserService:
    async def create_user_profile(self, *a, **k):
        raise RuntimeError("boom")

    async def get_user_profile(self, *a, **k):
        raise RuntimeError("boom")

    async def update_user_profile(self, *a, **k):
        raise RuntimeError("boom")

    async def update_user_preferences(self, *a, **k):
        raise RuntimeError("boom")

    async def record_interaction(self, *a, **k):
        raise RuntimeError("boom")

    async def get_interaction_history(self, *a, **k):
        raise RuntimeError("boom")

    async def generate_user_insights(self, *a, **k):
        raise RuntimeError("boom")

    async def delete_user_profile(self, *a, **k):
        raise RuntimeError("boom")


def _override_user_boom(_request: Request):
    return _BoomUserService()


@pytest.fixture
def override_user():
    app.dependency_overrides[get_user_service] = _override_user_boom
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_u(override_user):
    with TestClient(app) as c:
        yield c


def test_create_profile_500(client_u):
    r = client_u.post(
        "/api/v1/users/profile",
        json={
            "user_id": "x",
            "name": "N",
            "email": "a@b.c",
            "preferences": {
                "preferences": [],
                "budget_range": {"min": 1, "max": 2},
                "travel_style": "mid-range",
                "group_size": 1,
                "accessibility_needs": [],
                "dietary_restrictions": [],
                "language_preferences": ["English"],
            },
            "travel_history": [],
        },
    )
    assert r.status_code == 500


def test_get_profile_500(client_u):
    assert client_u.get("/api/v1/users/profile/u1").status_code == 500


def test_update_profile_500(client_u):
    r = client_u.put(
        "/api/v1/users/profile/u1",
        json={"location": "Berlin"},
    )
    assert r.status_code == 500


def test_update_preferences_500(client_u):
    r = client_u.post(
        "/api/v1/users/preferences/u1",
        json={
            "preferences": [],
            "budget_range": {"min": 1, "max": 2},
            "travel_style": "mid-range",
            "group_size": 1,
            "accessibility_needs": [],
            "dietary_restrictions": [],
            "language_preferences": ["English"],
        },
    )
    assert r.status_code == 500


def test_interaction_500(client_u):
    r = client_u.post(
        "/api/v1/users/interaction",
        json={
            "user_id": "u1",
            "activity_id": "a1",
            "interaction_type": "view",
        },
    )
    assert r.status_code == 500


def test_history_500(client_u):
    assert client_u.get("/api/v1/users/history/u1").status_code == 500


def test_insights_500(client_u):
    assert client_u.get("/api/v1/users/insights/u1").status_code == 500


def test_delete_500(client_u):
    assert client_u.delete("/api/v1/users/profile/u1").status_code == 500
