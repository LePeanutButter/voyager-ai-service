def test_menu_adaptation(client):
    r = client.get("/api/v1/adaptive-ui/menu/user-x")
    assert r.status_code == 200
    assert "primary_items" in r.json()


def test_home_feed(client):
    r = client.get("/api/v1/adaptive-ui/home-feed/user-x")
    assert r.status_code == 200
    assert "sections" in r.json()


def test_menu_adaptation_internal_error(client, monkeypatch):
    def boom(_user_id):
        raise RuntimeError("menu down")

    monkeypatch.setattr(client.app.state.adaptive_ui_service, "build_menu_adaptation", boom)
    r = client.get("/api/v1/adaptive-ui/menu/user-x")
    assert r.status_code == 500


def test_home_feed_internal_error(client, monkeypatch):
    def boom(_user_id):
        raise RuntimeError("feed down")

    monkeypatch.setattr(client.app.state.adaptive_ui_service, "build_home_feed_layout", boom)
    r = client.get("/api/v1/adaptive-ui/home-feed/user-x")
    assert r.status_code == 500
