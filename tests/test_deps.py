"""Unit tests for centralized FastAPI dependencies."""

import pytest
from fastapi import HTTPException

from app.api import deps


def _request_with_state(**attrs):
    class _App:
        def __init__(self, state):
            self.state = state

    class _State:
        pass

    st = _State()
    for k, v in attrs.items():
        setattr(st, k, v)

    class _Req:
        app = _App(st)

    return _Req()


def test_get_user_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_user_service(req)
    assert exc.value.status_code == 503


def test_get_matching_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_matching_service(req)
    assert exc.value.status_code == 503


def test_get_seasonality_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_seasonality_service(req)
    assert exc.value.status_code == 503


def test_get_trends_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_trends_service(req)
    assert exc.value.status_code == 503


def test_get_behavior_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_behavior_service(req)
    assert exc.value.status_code == 503


def test_get_adaptive_ui_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_adaptive_ui_service(req)
    assert exc.value.status_code == 503


def test_get_chat_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_chat_service(req)
    assert exc.value.status_code == 503


def test_get_preference_service_missing():
    req = _request_with_state()
    with pytest.raises(HTTPException) as exc:
        deps.get_preference_questionnaire_service(req)
    assert exc.value.status_code == 503


def test_require_model_manager_not_ready():
    class _MM:
        def is_ready(self):
            return False

    req = _request_with_state(model_manager=_MM())
    with pytest.raises(HTTPException) as exc:
        deps._require_model_manager(req)
    assert exc.value.status_code == 503


def test_require_model_manager_ready():
    class _MM:
        def is_ready(self):
            return True

    req = _request_with_state(model_manager=_MM())
    mm = deps._require_model_manager(req)
    assert mm is not None and mm.is_ready()
