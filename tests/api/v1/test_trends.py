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


def test_ingest_signals_returns_500_when_refresh_fails(client, monkeypatch):
    svc = client.app.state.trends_service

    async def boom():
        raise RuntimeError("refresh failure")

    monkeypatch.setattr(svc, "refresh", boom)
    payload = {
        "rows": [
            {
                "destination_id": "dst_err",
                "name": "Err",
                "country": "X",
                "tags": [],
                "previous": 1,
                "current": 2,
            }
        ]
    }
    r = client.post("/api/v1/trends/ingest/signals", json=payload)
    assert r.status_code == 500


def test_ingest_segments_returns_500_on_failure(client, monkeypatch):
    def boom(_segments):
        raise RuntimeError("segment ingest")

    monkeypatch.setattr(client.app.state.trends_service, "ingest_segment_library", boom)
    r = client.post("/api/v1/trends/ingest/segments", json={"segments": {"seg_a": {"label": "A"}}})
    assert r.status_code == 500
