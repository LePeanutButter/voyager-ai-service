"""
Shared fixtures: FastAPI TestClient runs real lifespan (in-memory ML models).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import database as db_database
from app.db.runtime_models import (
    BehaviorEventRecord,
    ChatMessageRecord,
    ChatSessionRecord,
    MatchingConnectionRecord,
    MatchingProfileRecord,
    PreferenceSessionRecord,
    SeasonalityProfileRecord,
    TrendSegmentRecord,
    TrendSignalRecord,
    UserInteractionRecord,
    UserProfileRecord,
)
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """HTTP client against the full app (startup/shutdown executed)."""
    with TestClient(app) as c:
        db_database.init_db_engine()
        assert db_database.SessionLocal is not None
        with db_database.SessionLocal() as db:
            for model in (
                BehaviorEventRecord,
                ChatMessageRecord,
                ChatSessionRecord,
                MatchingConnectionRecord,
                MatchingProfileRecord,
                PreferenceSessionRecord,
                SeasonalityProfileRecord,
                TrendSegmentRecord,
                TrendSignalRecord,
                UserInteractionRecord,
                UserProfileRecord,
            ):
                db.query(model).delete()
            db.commit()

        # Baseline ingests for data-driven modules used by API tests.
        app.state.trends_service.ingest_signal_rows(
            [
                {
                    "destination_id": "dst_barcelona",
                    "name": "Barcelona",
                    "country": "Spain",
                    "tags": ["cultural", "foodie"],
                    "previous": 90,
                    "current": 120,
                }
            ]
        )
        app.state.trends_service.ingest_segment_library(
            {
                "culture_seekers": {
                    "label": "Culture Seekers",
                    "seasonal": [{"label": "primavera", "intensity": 0.7, "months_peak": [4, 5]}],
                    "budget": {"avg_daily_budget": 120, "currency": "EUR"},
                    "preferences": ["cultural", "foodie"],
                },
                "family_budget": {
                    "label": "Family Budget",
                    "seasonal": [{"label": "verano", "intensity": 0.8, "months_peak": [7, 8]}],
                    "budget": {"avg_daily_budget": 90, "currency": "EUR"},
                    "preferences": ["family", "budget"],
                },
            }
        )
        app.state.seasonality_service.ingest_profiles(
            [
                {
                    "destination_id": "dst_barcelona",
                    "name": "Barcelona",
                    "country": "Spain",
                    "monthly_indices": [0.8, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.3, 1.2, 1.0, 0.9, 0.8],
                },
                {
                    "destination_id": "dst_lisbon",
                    "name": "Lisbon",
                    "country": "Portugal",
                    "monthly_indices": [0.7, 0.8, 0.9, 1.0, 1.0, 1.1, 1.2, 1.2, 1.1, 1.0, 0.9, 0.8],
                },
                {
                    "destination_id": "dst_kyoto",
                    "name": "Kyoto",
                    "country": "Japan",
                    "monthly_indices": [0.7, 0.7, 0.9, 1.1, 1.2, 1.0, 0.9, 0.9, 1.0, 1.1, 1.2, 0.8],
                },
                {
                    "destination_id": "dst_patagonia",
                    "name": "Patagonia",
                    "country": "Argentina",
                    "monthly_indices": [0.8, 0.8, 0.9, 1.0, 1.0, 1.1, 1.1, 1.0, 0.9, 0.9, 0.8, 0.8],
                },
            ]
        )
        app.state.matching_service.ingest_profiles(
            [
                {
                    "user_id": "user1",
                    "name": "User One",
                    "location": "Barcelona",
                    "preferences": ["cultural", "foodie"],
                },
                {
                    "user_id": "user2",
                    "name": "User Two",
                    "location": "Barcelona",
                    "preferences": ["cultural", "adventure"],
                },
            ]
        )
        yield c


@pytest.fixture
def sample_user_profile_payload() -> dict:
    """Minimal valid profile for POST /api/v1/users/profile."""
    return {
        "user_id": "test-user-1",
        "name": "Test User",
        "email": "test@example.com",
        "preferences": {
            "preferences": ["cultural", "adventure", "foodie"],
            "budget_range": {"min": 50, "max": 250},
            "travel_style": "mid-range",
            "group_size": 2,
            "accessibility_needs": [],
            "dietary_restrictions": [],
            "language_preferences": ["English"],
        },
        "travel_history": [],
    }


@pytest.fixture
def matching_find_payload() -> dict:
    """Body for POST /api/v1/matching/find (needs existing user profile)."""
    return {
        "user_id": "test-user-1",
        "location": {
            "latitude": 41.39,
            "longitude": 2.15,
            "city": "Barcelona",
            "country": "Spain",
            "radius_km": 50,
        },
        "preferences": ["cultural", "foodie"],
        "max_matches": 5,
    }


@pytest.fixture
def recommendation_request_payload() -> dict:
    return {
        "user_id": "test-user-1",
        "location": {
            "latitude": 41.39,
            "longitude": 2.15,
            "city": "Barcelona",
            "country": "Spain",
            "radius_km": 25,
        },
        "max_results": 5,
    }
