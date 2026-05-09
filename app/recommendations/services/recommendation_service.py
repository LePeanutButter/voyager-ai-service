"""Recommendation service backed by local AI SQLite data."""

from __future__ import annotations

from typing import Any, Dict, List

from app.recommendations.sqlite.repository import RecommendationRepository


class RealRecommendationService:
    """Generates recommendations from local AI data keyed by user_id."""

    def __init__(self) -> None:
        self.repo = RecommendationRepository()

    def recommend(
        self,
        user_id: str,
        query_text: str,
        candidates: List[Dict[str, Any]],
        limit: int = 8,
    ) -> Dict[str, Any]:
        user = self.repo.get_user_profile(user_id)
        prefs = self.repo.get_user_preferences(user_id)
        interactions = self.repo.get_recent_interactions(user_id, limit=25)
        ranked = self.repo.rank_items(
            query_text=query_text,
            candidates=candidates,
            limit=limit,
        )

        reranked = self._rerank_with_preferences(ranked, prefs)
        return {
            "user": user,
            "preferences": prefs,
            "recent_interactions": interactions,
            "items": reranked,
        }

    def record_feedback(self, user_id: str, item_id: str, rating: int) -> None:
        normalized = max(1, min(5, int(rating))) / 5.0
        self.repo.track_recommendation_feedback(user_id=user_id, item_id=item_id, rating=normalized)

    def _rerank_with_preferences(
        self,
        ranked: List[Dict[str, Any]],
        preferences: List[str],
    ) -> List[Dict[str, Any]]:
        pref_set = {p.lower() for p in preferences}
        scored: List[Dict[str, Any]] = []
        for item in ranked:
            category = str(item.get("category", "")).lower()
            pref_boost = 0.08 if category in pref_set else 0.0
            similarity = float(item.get("similarity", 0.0))
            final_score = max(0.0, min(1.0, similarity + pref_boost))
            row = dict(item)
            row["score"] = round(final_score, 6)
            scored.append(row)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored
