def test_local_recommendations_ok(client):
    r = client.post(
        "/api/v1/local/recommendations",
        json={
            "user_id": "test-user-1",
            "query": "arte y museos",
            "limit": 3,
            "candidates": [
                {
                    "id": "a1",
                    "name": "Museo del Prado",
                    "category": "cultural",
                    "price": 18,
                    "content_text": "arte clasico y moderno",
                },
                {
                    "id": "a2",
                    "name": "Parque del Retiro",
                    "category": "nature",
                    "price": 0,
                    "content_text": "parque urbano para caminar",
                },
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert len(body["items"]) > 0


def test_local_recommendations_validation(client):
    r = client.post(
        "/api/v1/local/recommendations",
        json={"user_id": "u1", "query": "x", "limit": 3, "candidates": []},
    )
    assert r.status_code == 422


def test_feedback_validation(client):
    r = client.post(
        "/api/v1/local/recommendations/feedback",
        params={"user_id": "u1", "item_id": "a1", "rating": 10},
    )
    assert r.status_code == 400


def test_feedback_ok(client):
    r = client.post(
        "/api/v1/local/recommendations/feedback",
        params={"user_id": "u1", "item_id": "a1", "rating": 4},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Feedback recorded successfully"

