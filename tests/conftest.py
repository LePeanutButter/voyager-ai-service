"""
Shared fixtures: FastAPI TestClient runs real lifespan (in-memory ML models).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """HTTP client against the full app (startup/shutdown executed)."""
    with TestClient(app) as c:
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
