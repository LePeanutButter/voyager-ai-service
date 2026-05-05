"""Additional router 500 paths: matching, trends, preferences questionnaire."""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.api.deps import (
    get_matching_service,
    get_preference_questionnaire_service,
    get_trends_service,
)
from app.main import app


class _BoomMatching:
    async def find_travel_partners(self, *a, **k):
        raise RuntimeError("boom")

    async def calculate_compatibility(self, *a, **k):
        raise RuntimeError("boom")

    async def initiate_connection(self, *a, **k):
        raise RuntimeError("boom")

    async def get_user_connections(self, *a, **k):
        raise RuntimeError("boom")

    async def respond_to_connection(self, *a, **k):
        raise RuntimeError("boom")

    async def get_travel_buddy_recommendations(self, *a, **k):
        raise RuntimeError("boom")

    async def process_connection_outcome(self, *a, **k):
        raise RuntimeError("boom")

    async def record_match_feedback(self, *a, **k):
        raise RuntimeError("boom")


def _ov_matching(_request: Request):
    return _BoomMatching()


@pytest.fixture
def client_matching_boom():
    app.dependency_overrides[get_matching_service] = _ov_matching
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_matching_find_500(client_matching_boom):
    r = client_matching_boom.post(
        "/api/v1/matching/find",
        json={
            "user_id": "user1",
            "location": {
                "latitude": 0.0,
                "longitude": 0.0,
                "city": "X",
                "country": "Y",
                "radius_km": 10,
            },
            "max_matches": 3,
        },
    )
    assert r.status_code == 500


def test_matching_compatibility_500(client_matching_boom):
    assert (
        client_matching_boom.get("/api/v1/matching/compatibility/user1/user2").status_code == 500
    )


def test_matching_connect_500(client_matching_boom):
    assert (
        client_matching_boom.post("/api/v1/matching/connect/u1/u2").status_code == 500
    )


def test_matching_connections_500(client_matching_boom):
    assert client_matching_boom.get("/api/v1/matching/connections/u1").status_code == 500


def test_matching_respond_500(client_matching_boom):
    r = client_matching_boom.put(
        "/api/v1/matching/connections/c1/respond",
        params={"response": "accept"},
    )
    assert r.status_code == 500


def test_matching_recommendations_500(client_matching_boom):
    assert (
        client_matching_boom.get("/api/v1/matching/recommendations/user1").status_code == 500
    )


def test_matching_outcome_500(client_matching_boom):
    r = client_matching_boom.post(
        "/api/v1/matching/learning/connection-outcome",
        json={
            "user_id": "user1",
            "target_user_id": "user2",
            "outcome": "success",
        },
    )
    assert r.status_code == 500


def test_matching_feedback_500(client_matching_boom):
    r = client_matching_boom.post(
        "/api/v1/matching/feedback/user1/user2",
        params={"rating": 4},
    )
    assert r.status_code == 500


class _BoomTrends:
    async def ensure_initialized(self):
        raise RuntimeError("boom")

    def get_dashboard(self):
        return {}

    def get_segment_insights(self, _sid):
        return {}

    def get_weekly_digest(self):
        return {}


def _ov_trends(_request: Request):
    return _BoomTrends()


@pytest.fixture
def client_trends_boom():
    app.dependency_overrides[get_trends_service] = _ov_trends
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_trends_dashboard_500(client_trends_boom):
    assert client_trends_boom.get("/api/v1/trends/dashboard").status_code == 500


def test_trends_segment_500(client_trends_boom):
    assert (
        client_trends_boom.get("/api/v1/trends/segments/s1/insights").status_code == 500
    )


def test_trends_weekly_500(client_trends_boom):
    assert client_trends_boom.get("/api/v1/trends/weekly-digest").status_code == 500


class _BoomPrefs:
    async def process_step(self, *a, **k):
        raise RuntimeError("boom")

    async def submit(self, *a, **k):
        raise RuntimeError("boom")


def _ov_prefs(_request: Request):
    return _BoomPrefs()


@pytest.fixture
def client_prefs_boom():
    app.dependency_overrides[get_preference_questionnaire_service] = _ov_prefs
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_prefs_step_500(client_prefs_boom):
    r = client_prefs_boom.post(
        "/api/v1/travel-preferences/questionnaire/step",
        json={"user_id": "u1", "answers": []},
    )
    assert r.status_code == 500


def test_prefs_submit_500(client_prefs_boom):
    r = client_prefs_boom.post(
        "/api/v1/travel-preferences/questionnaire/submit",
        json={
            "user_id": "u1",
            "session_id": "00000000-0000-0000-0000-000000000001",
            "answers": [],
        },
    )
    assert r.status_code == 500


class _PrefsStepValueError:
    async def process_step(self, *a, **k):
        raise ValueError("bad step")


def _ov_prefs_step_val(_request: Request):
    return _PrefsStepValueError()


@pytest.fixture
def client_prefs_step_val():
    app.dependency_overrides[get_preference_questionnaire_service] = _ov_prefs_step_val
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_prefs_step_400_validation(client_prefs_step_val):
    r = client_prefs_step_val.post(
        "/api/v1/travel-preferences/questionnaire/step",
        json={"user_id": "u1", "answers": []},
    )
    assert r.status_code == 400


class _PrefsSubmitValueError:
    async def submit(self, *a, **k):
        raise ValueError("not done")


def _ov_prefs_submit_val(_request: Request):
    return _PrefsSubmitValueError()


@pytest.fixture
def client_prefs_submit_val():
    app.dependency_overrides[get_preference_questionnaire_service] = _ov_prefs_submit_val
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_prefs_submit_400_validation(client_prefs_submit_val):
    r = client_prefs_submit_val.post(
        "/api/v1/travel-preferences/questionnaire/submit",
        json={
            "user_id": "u1",
            "session_id": "00000000-0000-0000-0000-000000000002",
            "answers": [],
        },
    )
    assert r.status_code == 400
