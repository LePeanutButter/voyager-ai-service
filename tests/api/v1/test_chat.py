def test_chat_post(client):
    r = client.post(
        "/api/v1/chat",
        json={"userId": "chat-u1", "message": "Plan a weekend in Porto"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "reply" in body
    assert "metadata" in body

    h = client.get("/api/v1/chat/chat-u1/history")
    assert h.status_code == 200
    assert h.json()["total_messages"] >= 1

    cl = client.delete("/api/v1/chat/chat-u1/history")
    assert cl.status_code == 200


def test_chat_validation(client):
    r = client.post(
        "/api/v1/chat",
        json={"userId": "", "message": "x"},
    )
    assert r.status_code == 422


def test_history_not_found(client):
    r = client.get("/api/v1/chat/unknown-user-999/history")
    assert r.status_code == 404


def test_clear_not_found(client):
    r = client.delete("/api/v1/chat/unknown-user-999/history")
    assert r.status_code == 404
