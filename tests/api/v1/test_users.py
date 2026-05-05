"""Tests for /api/v1/users/*."""


def test_create_and_get_profile(client, sample_user_profile_payload):
    r = client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    assert r.status_code == 200

    r2 = client.get("/api/v1/users/profile/test-user-1")
    assert r2.status_code == 200
    assert r2.json()["email"] == "test@example.com"


def test_get_profile_not_found(client):
    r = client.get("/api/v1/users/profile/does-not-exist")
    assert r.status_code == 404


def test_update_profile(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.put(
        "/api/v1/users/profile/test-user-1",
        json={"location": "Madrid"},
    )
    assert r.status_code == 200
    assert r.json()["location"] == "Madrid"


def test_preferences_update(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post(
        "/api/v1/users/preferences/test-user-1",
        json={
            "preferences": ["beach", "relaxation"],
            "budget_range": {"min": 80, "max": 300},
            "travel_style": "luxury",
            "group_size": 2,
            "accessibility_needs": [],
            "dietary_restrictions": [],
            "language_preferences": ["English"],
        },
    )
    assert r.status_code == 200


def test_interaction_and_history(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post(
        "/api/v1/users/interaction",
        json={
            "user_id": "test-user-1",
            "activity_id": "act1",
            "interaction_type": "view",
        },
    )
    assert r.status_code == 200

    h = client.get("/api/v1/users/history/test-user-1")
    assert h.status_code == 200
    assert h.json()["total_count"] >= 1


def test_insights(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.get("/api/v1/users/insights/test-user-1")
    assert r.status_code == 200


def test_delete_profile(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.delete("/api/v1/users/profile/test-user-1")
    assert r.status_code == 200
