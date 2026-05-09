def test_trends_dashboard(client):
    r = client.get("/api/v1/trends/dashboard")
    assert r.status_code == 200
    assert "emerging_destinations" in r.json()


def test_segment_insights(client):
    r = client.get("/api/v1/trends/segments/family_budget/insights")
    assert r.status_code == 200


def test_weekly_digest(client):
    r = client.get("/api/v1/trends/weekly-digest")
    assert r.status_code == 200
    data = r.json()
    assert "micro_trends" in data
    assert len(data["micro_trends"]) >= 1
    geo = data["micro_trends"][0].get("geo")
    assert geo is not None
    assert geo.get("name")
    assert geo.get("country")
