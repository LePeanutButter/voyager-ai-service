"""User profile and interaction service backed by DB runtime tables."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select

from app.db import database as db_database
from app.db.runtime_models import UserInteractionRecord, UserProfileRecord
from app.modules.users.schemas import UserInteraction, UserPreferences, UserProfile, UserProfileUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, model_manager):
        self.model_manager = model_manager
        db_database.init_db_engine()

    @staticmethod
    def _db():
        assert db_database.SessionLocal is not None
        return db_database.SessionLocal()

    def create_user_profile(self, profile: UserProfile) -> UserProfile:
        if "@" not in profile.email:
            raise ValueError("Invalid email format")
        prefs = self._analyze_preferences(profile.preferences)
        now = datetime.now(timezone.utc)
        with self._db() as db:
            if db.get(UserProfileRecord, profile.user_id):
                raise ValueError(f"User profile {profile.user_id} already exists")
            db.add(
                UserProfileRecord(
                    user_id=profile.user_id,
                    name=profile.name,
                    email=profile.email,
                    age=profile.age,
                    location=profile.location,
                    preferences_json=prefs.model_dump_json(),
                    travel_history_json=json.dumps(profile.travel_history),
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()
        return UserProfile(
            user_id=profile.user_id,
            name=profile.name,
            email=profile.email,
            age=profile.age,
            location=profile.location,
            preferences=prefs,
            travel_history=profile.travel_history,
            created_at=now,
            updated_at=now,
        )

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        with self._db() as db:
            row = db.get(UserProfileRecord, user_id)
            if not row:
                return None
            return UserProfile(
                user_id=row.user_id,
                name=row.name,
                email=row.email,
                age=row.age,
                location=row.location,
                preferences=UserPreferences(**json.loads(row.preferences_json)),
                travel_history=json.loads(row.travel_history_json or "[]"),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def update_user_profile(self, user_id: str, profile_update: UserProfileUpdate) -> Optional[UserProfile]:
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
        if profile_update.preferences:
            profile.preferences = self._analyze_preferences(profile_update.preferences)
        if profile_update.location is not None:
            profile.location = profile_update.location
        if profile_update.travel_history is not None:
            profile.travel_history = profile_update.travel_history
        profile.updated_at = datetime.now(timezone.utc)
        with self._db() as db:
            row = db.get(UserProfileRecord, user_id)
            if not row:
                return None
            row.location = profile.location
            row.preferences_json = profile.preferences.model_dump_json()
            row.travel_history_json = json.dumps(profile.travel_history)
            row.updated_at = profile.updated_at
            db.commit()
        return profile

    def update_user_preferences(self, user_id: str, preferences: UserPreferences) -> bool:
        profile = self.get_user_profile(user_id)
        if not profile:
            return False
        profile.preferences = self._analyze_preferences(preferences)
        profile.updated_at = datetime.now(timezone.utc)
        with self._db() as db:
            row = db.get(UserProfileRecord, user_id)
            if not row:
                return False
            row.preferences_json = profile.preferences.model_dump_json()
            row.updated_at = profile.updated_at
            db.commit()
        return True

    def record_interaction(self, interaction: UserInteraction):
        with self._db() as db:
            db.add(
                UserInteractionRecord(
                    user_id=interaction.user_id,
                    activity_id=interaction.activity_id,
                    interaction_type=interaction.interaction_type,
                    timestamp=interaction.timestamp or datetime.now(timezone.utc),
                    metadata_json=json.dumps(interaction.metadata or {}),
                )
            )
            db.commit()
        self._update_preferences_from_interaction(interaction)

    def get_interaction_history(self, user_id: str, limit: int) -> List[UserInteraction]:
        with self._db() as db:
            rows = db.scalars(
                select(UserInteractionRecord)
                .where(UserInteractionRecord.user_id == user_id)
                .order_by(desc(UserInteractionRecord.timestamp), desc(UserInteractionRecord.id))
                .limit(limit)
            ).all()
        rows = list(reversed(rows))
        return [
            UserInteraction(
                user_id=r.user_id,
                activity_id=r.activity_id,
                interaction_type=r.interaction_type,
                timestamp=r.timestamp,
                metadata=json.loads(r.metadata_json or "{}"),
            )
            for r in rows
        ]

    def generate_user_insights(self, user_id: str) -> Optional[Dict[str, Any]]:
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
        interactions = self.get_interaction_history(user_id, limit=500)
        interaction_count = len(interactions)
        categories: Dict[str, int] = {}
        for i in interactions:
            cat = (i.metadata or {}).get("category")
            if cat:
                categories[cat] = categories.get(cat, 0) + 1
        positives = sum(
            1 for i in interactions if i.interaction_type in {"book", "bookmark", "click", "rate", "view"}
        )
        return {
            "user_id": user_id,
            "interaction_count": interaction_count,
            "top_categories": sorted(categories.items(), key=lambda kv: kv[1], reverse=True)[:5],
            "recommendation_accuracy": round(positives / max(interaction_count, 1), 4),
            "profile": profile.model_dump(),
        }

    def delete_user_profile(self, user_id: str) -> bool:
        with self._db() as db:
            row = db.get(UserProfileRecord, user_id)
            if not row:
                return False
            db.delete(row)
            for inter in db.scalars(
                select(UserInteractionRecord).where(UserInteractionRecord.user_id == user_id)
            ).all():
                db.delete(inter)
            db.commit()
            return True

    def _analyze_preferences(self, preferences: UserPreferences) -> UserPreferences:
        if not preferences.budget_range:
            preferences.budget_range = {"min": 0, "max": 0}
        if preferences.budget_range.get("min", 0) < 0:
            preferences.budget_range["min"] = 0
        if preferences.budget_range.get("max", 0) < preferences.budget_range.get("min", 0):
            preferences.budget_range["max"] = preferences.budget_range["min"]
        return preferences

    def _update_preferences_from_interaction(self, interaction: UserInteraction):
        profile = self.get_user_profile(interaction.user_id)
        if not profile:
            return
        prefs = list(profile.preferences.preferences)
        if interaction.interaction_type in {"book", "bookmark", "click"}:
            cat = (interaction.metadata or {}).get("category")
            if cat:
                try:
                    enum_v = type(profile.preferences.preferences[0])(cat) if profile.preferences.preferences else None
                except Exception:
                    enum_v = None
                if enum_v and enum_v not in prefs:
                    prefs.append(enum_v)
                    profile.preferences.preferences = prefs
                    self.update_user_preferences(interaction.user_id, profile.preferences)

