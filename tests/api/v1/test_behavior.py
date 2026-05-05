from app.modules.common.schemas.enums import InteractionType


def test_track_and_analyze(client):
    r = client.post(
        "/api/v1/behavior-analysis/track",
        json={
            "user_id": "beh-user",
            "interaction_type": InteractionType.CLICK.value,
            "activity_category": "cultural",
            "context": {"nav_item_id": "matching"},
        },
    )
    assert r.status_code == 200

    for _ in range(6):
        client.post(
            "/api/v1/behavior-analysis/track",
            json={
                "user_id": "beh-user",
                "interaction_type": InteractionType.VIEW.value,
                "activity_category": "outdoor",
            },
        )

    r2 = client.post(
        "/api/v1/behavior-analysis/analyze",
        json={
            "user_id": "beh-user",
            "analysis_period_days": 30,
            "include_patterns": True,
            "include_preference_updates": True,
        },
    )
    assert r2.status_code == 200


def test_analyze_unknown_user(client):
    r = client.post(
        "/api/v1/behavior-analysis/analyze",
        json={"user_id": "unknown-behavior", "analysis_period_days": 7},
    )
    assert r.status_code == 400


def test_summary_not_found(client):
    r = client.get("/api/v1/behavior-analysis/summary/ghost-user")
    assert r.status_code == 404


def test_batch_track(client):
    r = client.post(
        "/api/v1/behavior-analysis/batch-track",
        json=[
            {
                "user_id": "batch-u",
                "interaction_type": InteractionType.CLICK.value,
            },
            {
                "user_id": "batch-u",
                "interaction_type": InteractionType.VIEW.value,
            },
        ],
    )
    assert r.status_code == 200


def test_patterns_insufficient_data(client):
    r = client.get("/api/v1/behavior-analysis/patterns/new-user-xyz", params={"days": 7})
    assert r.status_code == 400


def test_clear_behavior(client):
    client.post(
        "/api/v1/behavior-analysis/track",
        json={
            "user_id": "clear-me",
            "interaction_type": InteractionType.CLICK.value,
        },
    )
    r = client.delete("/api/v1/behavior-analysis/clear/clear-me")
    assert r.status_code == 200
