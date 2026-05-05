"""Tests for /api/v1/matching/*."""

from app.modules.common.schemas.enums import ConnectionOutcome


def test_find_requires_profile(client, sample_user_profile_payload, matching_find_payload):
    p = {**sample_user_profile_payload, "user_id": "user1", "email": "user1@example.com"}
    client.post("/api/v1/users/profile", json=p)
    body = {**matching_find_payload, "user_id": "user1"}
    r = client.post("/api/v1/matching/find", json=body)
    assert r.status_code == 200
    data = r.json()
    assert "matches" in data
    assert data["user_id"] == "user1"


def test_find_fails_missing_user(client, matching_find_payload):
    payload = {**matching_find_payload, "user_id": "nonexistent-user-zzz"}
    r = client.post("/api/v1/matching/find", json=payload)
    assert r.status_code == 500


def test_compatibility_not_found(client):
    r = client.get("/api/v1/matching/compatibility/nobody1/nobody2")
    assert r.status_code == 404


def test_connection_flow(client, sample_user_profile_payload, matching_find_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post(
        "/api/v1/matching/connect/test-user-1/partner-9",
        params={"message": "hola"},
    )
    assert r.status_code == 200
    assert "connection_id" in r.json()

    r2 = client.get("/api/v1/matching/connections/test-user-1")
    assert r2.status_code == 200

    r3 = client.get("/api/v1/matching/recommendations/test-user-1", params={"limit": 2})
    assert r3.status_code == 200


def test_respond_connection_invalid(client):
    r = client.put(
        "/api/v1/matching/connections/abc/respond",
        params={"response": "maybe"},
    )
    assert r.status_code == 400


def test_match_feedback_validation(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post(
        "/api/v1/matching/feedback/test-user-1/p2",
        params={"rating": 0},
    )
    assert r.status_code == 400

    r2 = client.post(
        "/api/v1/matching/feedback/test-user-1/p2",
        params={"rating": 5},
    )
    assert r2.status_code == 200


def test_connection_outcome(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post(
        "/api/v1/matching/learning/connection-outcome",
        json={
            "user_id": "test-user-1",
            "target_user_id": "mate-2",
            "outcome": ConnectionOutcome.SUCCESS.value,
            "dimension_snapshot": {"interests": 0.8},
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
