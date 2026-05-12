"""Tests unitarios adicionales para TrendsService (surge, segmentos, digest)."""

from __future__ import annotations

import pytest

from app.modules.trends.service import TrendsService


@pytest.fixture
def trends_no_db(monkeypatch):
    monkeypatch.setattr(TrendsService, "_load_ingested_state", lambda self: None)
    return TrendsService()


@pytest.mark.asyncio
async def test_refresh_surge_when_previous_zero_or_negative(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._signal_rows = [
        {
            "destination_id": "a",
            "name": "A",
            "country": "C",
            "tags": [],
            "previous": 0,
            "current": 10,
        },
        {
            "destination_id": "b",
            "name": "B",
            "country": "C",
            "tags": [],
            "previous": 0,
            "current": 0,
        },
    ]
    await svc.refresh()
    assert svc._emerging[0].surge_ratio == 1.0
    assert svc._emerging[1].surge_ratio == 0.0


@pytest.mark.asyncio
async def test_emerging_for_preferences_sort_and_filter(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._signal_rows = [
        {
            "destination_id": "high",
            "name": "H",
            "country": "C",
            "tags": ["cultural"],
            "previous": 100,
            "current": 250,
        },
        {
            "destination_id": "low",
            "name": "L",
            "country": "C",
            "tags": ["cultural"],
            "previous": 100,
            "current": 110,
        },
    ]
    await svc.refresh()
    cultural = svc.emerging_for_preferences({"cultural"})
    assert cultural[0]["surge_ratio"] >= cultural[-1]["surge_ratio"]
    assert svc.emerging_for_preferences({"beach"}) == []


def test_get_dashboard_raises_when_not_refreshed(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._emerging = []
    with pytest.raises(RuntimeError, match="not initialised"):
        svc.get_dashboard()


def test_get_segment_insights_unknown_segment_raises(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._segment_library = {}
    with pytest.raises(RuntimeError, match="not found"):
        svc.get_segment_insights("unknown_segment")


@pytest.mark.asyncio
async def test_ensure_initialized_errors_when_no_signals(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._signal_rows = []
    with pytest.raises(RuntimeError, match="ingest"):
        await svc.ensure_initialized()


@pytest.mark.asyncio
async def test_ensure_initialized_triggers_refresh_when_emerging_empty(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._signal_rows = [
        {
            "destination_id": "z",
            "name": "Z",
            "country": "C",
            "tags": [],
            "previous": 10,
            "current": 20,
        }
    ]
    svc._emerging = []
    await svc.ensure_initialized()
    assert svc._emerging


def test_get_full_signals_returns_shallow_copy(trends_no_db: TrendsService):
    svc = trends_no_db
    svc._emerging = []
    assert svc.get_full_signals() == []
