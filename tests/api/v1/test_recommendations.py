"""Integration tests: /api/v1/recommendations/*."""


def test_destinations_personalized(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    body = {
        "user_id": "test-user-1",
        "max_results": 4,
        "prefer_successful_patterns": True,
        "include_emerging_trends": False,
        "theme_weights": {"cultural": 1.0},
    }
    r = client.post("/api/v1/recommendations/destinations/personalized", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == "test-user-1"
    assert "destinations" in data
    assert isinstance(data["destinations"], list)


def test_contextual_activities(client, sample_user_profile_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post(
        "/api/v1/recommendations/activities/contextual",
        json={
            "user_id": "test-user-1",
            "latitude": 41.39,
            "longitude": 2.15,
            "city_hint": "Barcelona",
            "weather": "rain",
            "max_results": 4,
            "radius_km": 30,
        },
    )
    assert r.status_code == 200
    assert "activities" in r.json()


def test_personalized_recommendations(client, sample_user_profile_payload, recommendation_request_payload):
    client.post("/api/v1/users/profile", json=sample_user_profile_payload)
    r = client.post("/api/v1/recommendations/personalized", json=recommendation_request_payload)
    assert r.status_code == 200
    assert "recommendations" in r.json()


def test_popular_and_trending(client):
    r = client.get("/api/v1/recommendations/popular/Barcelona", params={"limit": 3})
    assert r.status_code == 200
    assert r.json()["location"] == "Barcelona"

    r2 = client.get("/api/v1/recommendations/trending", params={"limit": 2})
    assert r2.status_code == 200


def test_similar_activities(client):
    r = client.get("/api/v1/recommendations/similar/act_any", params={"limit": 2})
    assert r.status_code == 200


def test_feedback_validation(client):
    r = client.post(
        "/api/v1/recommendations/feedback",
        params={"user_id": "u1", "activity_id": "a1", "rating": 10},
    )
    assert r.status_code == 400


def test_feedback_ok(client):
    r = client.post(
        "/api/v1/recommendations/feedback",
        params={"user_id": "u1", "activity_id": "a1", "rating": 4},
    )
    assert r.status_code == 200


def test_categories(client):
    r = client.get("/api/v1/recommendations/categories")
    assert r.status_code == 200
    assert "categories" in r.json()


def test_destinations_uses_mock_profile_for_unknown_user(client):
    """Recommendation service returns a synthetic profile when no user record exists."""
    r = client.post(
        "/api/v1/recommendations/destinations/personalized",
        json={"user_id": "ghost-user-xyz", "max_results": 3, "include_emerging_trends": False},
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == "ghost-user-xyz"
