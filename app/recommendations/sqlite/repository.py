"""SQLite repository for local recommendation data keyed by user_id."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import desc, select

from app.database.ai_sqlite import (
    AIInteraction,
    AISessionLocal,
    AIUserPreference,
    AIUserProfile,
    now_utc,
)


class RecommendationRepository:
    """Recommendation persistence over local AI SQLite only."""

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        with AISessionLocal() as db:
            profile = db.get(AIUserProfile, user_id)
            if profile is None:
                return {
                    "id": user_id,
                    "name": "",
                    "segment": "external",
                }
            return {
                "id": profile.user_id,
                "name": profile.display_name or "",
                "segment": profile.segment,
            }

    def get_user_preferences(self, user_id: str) -> List[str]:
        with AISessionLocal() as db:
            rows = db.scalars(
                select(AIUserPreference.preference_key)
                .where(AIUserPreference.user_id == user_id)
                .order_by(desc(AIUserPreference.weight), AIUserPreference.preference_key.asc())
            ).all()
            return [str(r) for r in rows]

    def get_recent_interactions(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        with AISessionLocal() as db:
            rows = db.scalars(
                select(AIInteraction)
                .where(AIInteraction.user_id == user_id)
                .order_by(desc(AIInteraction.created_at), desc(AIInteraction.id))
                .limit(limit)
            ).all()
            return [
                {
                    "product_id": r.item_id,
                    "event_type": r.event_type,
                    "score": r.score,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    def rank_items(self, query_text: str, candidates: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        query = query_text.strip().lower()
        ranked: List[Dict[str, Any]] = []
        for item in candidates:
            name = str(item.get("name", ""))
            category = str(item.get("category", ""))
            content_text = str(item.get("content_text", ""))
            haystack = f"{name} {category} {content_text}".lower()
            similarity = 0.55
            if query and query in haystack:
                similarity = 0.78
            ranked.append(
                {
                    "id": str(item.get("id", "")),
                    "name": name,
                    "category": category,
                    "price": float(item.get("price", 0) or 0),
                    "similarity": similarity,
                }
            )
        ranked.sort(key=lambda x: x["similarity"], reverse=True)
        return ranked[:limit]

    def track_recommendation_feedback(self, user_id: str, item_id: str, rating: float) -> None:
        with AISessionLocal() as db:
            db.add(
                AIInteraction(
                    user_id=user_id,
                    item_id=item_id,
                    event_type="feedback",
                    score=max(0.0, min(1.0, rating)),
                    created_at=now_utc(),
                )
            )
            db.commit()

