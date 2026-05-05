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


def test_history_blank_user_id(client):
    r = client.get("/api/v1/chat/%20/history")
    assert r.status_code == 400


def test_clear_history_blank_user_id(client):
    r = client.delete("/api/v1/chat/%20/history")
    assert r.status_code == 400


def test_chat_internal_error(client, monkeypatch):
    async def boom(_request):
        raise RuntimeError("chat down")

    monkeypatch.setattr(client.app.state.chat_service, "handle_message", boom)
    r = client.post("/api/v1/chat", json={"userId": "chat-u2", "message": "hello"})
    assert r.status_code == 500


def test_get_history_internal_error(client, monkeypatch):
    def boom(_user_id):
        raise RuntimeError("history down")

    monkeypatch.setattr(client.app.state.chat_service, "get_history", boom)
    r = client.get("/api/v1/chat/chat-u1/history")
    assert r.status_code == 500


def test_clear_history_internal_error(client, monkeypatch):
    async def boom(_user_id):
        raise RuntimeError("clear down")

    monkeypatch.setattr(client.app.state.chat_service, "clear_history", boom)
    r = client.delete("/api/v1/chat/chat-u1/history")
    assert r.status_code == 500
