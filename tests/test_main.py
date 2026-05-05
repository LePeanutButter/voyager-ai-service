"""Root and health endpoints."""

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "version" in body


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert "models_loaded" in data


def test_health_handles_exception(client):
    class _BrokenManager:
        def is_ready(self):
            raise RuntimeError("simulated failure")

    saved = getattr(client.app.state, "model_manager", None)
    try:
        client.app.state.model_manager = _BrokenManager()
        r = client.get("/health")
        assert r.status_code == 503
    finally:
        client.app.state.model_manager = saved
