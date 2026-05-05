def test_menu_adaptation(client):
    r = client.get("/api/v1/adaptive-ui/menu/user-x")
    assert r.status_code == 200
    assert "primary_items" in r.json()


def test_home_feed(client):
    r = client.get("/api/v1/adaptive-ui/home-feed/user-x")
    assert r.status_code == 200
    assert "sections" in r.json()
