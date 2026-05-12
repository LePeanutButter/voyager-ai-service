"""API tests for /api/v1/seasonality (seasonality-aware demand & visibility)."""


def test_seasonality_overview(client):
    r = client.get("/api/v1/seasonality/overview")
    assert r.status_code == 200
    data = r.json()
    assert "destinations" in data
    assert "reference_month" in data
    assert len(data["destinations"]) >= 1


def test_seasonality_overview_reference_month(client):
    r = client.get("/api/v1/seasonality/overview", params={"reference_month": 8})
    assert r.status_code == 200
    assert r.json()["reference_month"] == 8


def test_seasonality_destination_profile(client):
    r = client.get("/api/v1/seasonality/destinations/dst_lisbon")
    assert r.status_code == 200
    body = r.json()
    assert body["destination_id"] == "dst_lisbon"
    assert len(body["monthly_indices"]) == 12


def test_seasonality_destination_not_found(client):
    r = client.get("/api/v1/seasonality/destinations/dst_does_not_exist")
    assert r.status_code == 404


def test_seasonality_forecast(client):
    r = client.post(
        "/api/v1/seasonality/forecast",
        json={
            "destination_id": "dst_barcelona",
            "start_month": 2,
            "horizon_months": 5,
        },
    )
    assert r.status_code == 200
    pts = r.json()["points"]
    assert len(pts) == 5


def test_seasonality_forecast_unknown_destination(client):
    r = client.post(
        "/api/v1/seasonality/forecast",
        json={"destination_id": "unknown", "start_month": 1, "horizon_months": 3},
    )
    assert r.status_code == 200
    assert r.json()["points"] == []


def test_seasonality_visibility_adjustments(client):
    r = client.post(
        "/api/v1/seasonality/visibility-adjustments",
        json={
            "destination_ids": ["dst_barcelona", "dst_patagonia"],
            "travel_month": 7,
            "apply_mitigation": True,
        },
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 2
    assert {rows[0]["destination_id"], rows[1]["destination_id"]} == {
        "dst_barcelona",
        "dst_patagonia",
    }


def test_seasonality_visibility_no_mitigation(client):
    r = client.post(
        "/api/v1/seasonality/visibility-adjustments",
        json={
            "destination_ids": ["dst_kyoto"],
            "travel_month": 4,
            "apply_mitigation": False,
        },
    )
    assert r.status_code == 200
    assert r.json()["rows"][0]["visibility_multiplier"] == 1.0


def test_seasonality_ingest_profiles_500(client, monkeypatch):
    def boom(_rows):
        raise RuntimeError("ingest profiles")

    monkeypatch.setattr(client.app.state.seasonality_service, "ingest_profiles", boom)
    row = {
        "destination_id": "dst_x",
        "name": "X",
        "country": "Y",
        "monthly_indices": [1.0] * 12,
    }
    r = client.post("/api/v1/seasonality/ingest/profiles", json={"rows": [row]})
    assert r.status_code == 500


def test_seasonality_overview_500(client, monkeypatch):
    def boom(reference_month=None):
        raise RuntimeError("overview")

    monkeypatch.setattr(client.app.state.seasonality_service, "overview", boom)
    r = client.get("/api/v1/seasonality/overview")
    assert r.status_code == 500


def test_seasonality_forecast_500(client, monkeypatch):
    def boom(destination_id, start_month, horizon_months):
        raise RuntimeError("forecast")

    monkeypatch.setattr(client.app.state.seasonality_service, "forecast_naive_seasonal", boom)
    r = client.post(
        "/api/v1/seasonality/forecast",
        json={"destination_id": "dst_barcelona", "start_month": 1, "horizon_months": 2},
    )
    assert r.status_code == 500


def test_seasonality_visibility_adjustments_500(client, monkeypatch):
    def boom(destination_ids, travel_month, apply_mitigation):
        raise RuntimeError("visibility")

    monkeypatch.setattr(client.app.state.seasonality_service, "visibility_adjustments", boom)
    r = client.post(
        "/api/v1/seasonality/visibility-adjustments",
        json={"destination_ids": ["dst_barcelona"], "travel_month": 6, "apply_mitigation": True},
    )
    assert r.status_code == 500
