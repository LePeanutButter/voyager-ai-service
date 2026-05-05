"""Questionnaire flow (multiple steps) + error paths."""


def _step(client, user_id, session_id, answers):
    return client.post(
        "/api/v1/travel-preferences/questionnaire/step",
        json={
            "user_id": user_id,
            "session_id": session_id,
            "answers": answers,
        },
    )


def test_questionnaire_happy_path_cultural(client):
    r0 = _step(
        client,
        "pref-user",
        None,
        [{"question_id": "primary_travel_style", "selected_option_ids": ["cultural"]}],
    )
    assert r0.status_code == 200
    sid = r0.json()["session_id"]
    assert r0.json()["is_complete"] is False

    r1 = _step(
        client,
        "pref-user",
        sid,
        [
            {"question_id": "culture_depth", "selected_option_ids": ["museums"]},
            {"question_id": "cultural_pace", "selected_option_ids": ["balanced_pace"]},
        ],
    )
    assert r1.status_code == 200
    assert r1.json()["is_complete"] is False

    r2 = _step(
        client,
        "pref-user",
        sid,
        [{"question_id": "trip_budget_band", "selected_option_ids": ["mid"]}],
    )
    assert r2.status_code == 200
    assert r2.json()["is_complete"] is True

    sub = client.post(
        "/api/v1/travel-preferences/questionnaire/submit",
        json={
            "user_id": "pref-user",
            "session_id": sid,
            "answers": [],
        },
    )
    assert sub.status_code == 200
    data = sub.json()
    assert data["primary_category"] == "cultural"
    assert "preference_profile" in data


def test_step_invalid_session(client):
    r = _step(
        client,
        "u1",
        "00000000-0000-0000-0000-000000000000",
        [],
    )
    assert r.status_code == 400
