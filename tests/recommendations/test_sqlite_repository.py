"""RecommendationRepository sobre AI SQLite (tests de integración ligeros)."""

from __future__ import annotations

import pytest

from app.database.ai_sqlite import AISessionLocal, AIUserProfile, init_ai_sqlite, now_utc
from app.recommendations.sqlite.repository import RecommendationRepository


@pytest.fixture(scope="module", autouse=True)
def _ai_sqlite_ready():
    init_ai_sqlite()


@pytest.fixture
def repo():
    return RecommendationRepository()


def test_get_user_profile_external_fallback(repo: RecommendationRepository):
    out = repo.get_user_profile("__repo_unknown_user__")
    assert out["segment"] == "external"


def test_get_user_profile_existing_row(repo: RecommendationRepository):
    uid = "__repo_profile_u__"
    with AISessionLocal() as db:
        db.merge(
            AIUserProfile(
                user_id=uid,
                display_name="Repo User",
                segment="premium",
                created_at=now_utc(),
                updated_at=now_utc(),
            )
        )
        db.commit()
    out = repo.get_user_profile(uid)
    assert out["name"] == "Repo User" and out["segment"] == "premium"


def test_rank_items_similarity_when_query_matches(repo: RecommendationRepository):
    items = [
        {"id": "1", "name": "Tour Roma", "category": "city", "content_text": "walking"},
        {"id": "2", "name": "Other", "category": "x", "content_text": "nothing"},
    ]
    ranked = repo.rank_items("roma", items, 5)
    assert ranked[0]["similarity"] >= ranked[-1]["similarity"]
