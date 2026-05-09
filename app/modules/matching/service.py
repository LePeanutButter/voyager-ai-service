"""Traveler matching: scoring, ranking, and connection lifecycle (data-driven).

Purpose:
    Score candidate travelers, explain multidimensional compatibility,
    and manage simple connection records with optional learning feedback.

Responsibilities:
    Profile resolution from ingested data, compatibility math, buddy lists,
    and weight updates via ``MatchingLearningStore``.

Dependencies:
    ``settings``, enums, ``matching.schemas``, ``model_manager``, ``MatchingLearningStore``.
"""

from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select

from app.modules.common.schemas.enums import ConnectionOutcome, TravelPreference
from app.modules.matching.schemas import (
    TravelerMatchRequest,
    TravelerMatch,
    MatchingResponse,
)
from app.core.config import settings
from app.db import database as db_database
from app.db.runtime_models import MatchingConnectionRecord, MatchingProfileRecord
from app.ml.learning_store import MatchingLearningStore

logger = logging.getLogger(__name__)


class MatchingService:
    """Orchestrates match discovery, scoring, and connection state.

    Attributes:
        model_manager: Loads optional ``traveler_matching_model`` for blended scores.
        learning_store: Persists and adjusts dimension weights from outcomes.
        connections: Connection documents persisted in runtime DB tables.
        user_profiles: Ingested profile map (resolved by ``_get_user_profile``).
    """

    def __init__(self, model_manager, learning_store: MatchingLearningStore):
        """Wires model access and the continuous-learning store (PBI 27).

        Args:
            model_manager: Shared model registry.
            learning_store: Store that records successes, incompatibilities, and ratings.
        """
        self.model_manager = model_manager
        self.learning_store = learning_store
        db_database.init_db_engine()
        self.user_profiles: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _db():
        assert db_database.SessionLocal is not None
        return db_database.SessionLocal()

    def ingest_profiles(self, profiles: List[Dict[str, Any]]) -> int:
        """Upsert profiles used by matching endpoints."""
        count = 0
        with self._db() as db:
            for p in profiles:
                user_id = str(p.get("user_id", "")).strip()
                if not user_id:
                    continue
                self.user_profiles[user_id] = dict(p)
                row = db.get(MatchingProfileRecord, user_id)
                payload = json.dumps(p)
                if row is None:
                    db.add(
                        MatchingProfileRecord(
                            user_id=user_id,
                            profile_json=payload,
                            updated_at=datetime.now(timezone.utc),
                        )
                    )
                else:
                    row.profile_json = payload
                    row.updated_at = datetime.now(timezone.utc)
                count += 1
            db.commit()
        logger.info("Matching profiles ingested: %s", count)
        return count
    
    def find_travel_partners(self, request: TravelerMatchRequest) -> MatchingResponse:
        """Scores candidates, filters by minimum compatibility, and returns ranked matches.

        Args:
            request: Seeker id, location/dates, preferences, and result cap.

        Returns:
            ``MatchingResponse`` with ``TravelerMatch`` rows and search metadata.

        Raises:
            ValueError: If the seeker's profile cannot be resolved.
            Exception: Logged and re-raised for upstream handling.
        """
        try:
            logger.info(f"Finding travel partners for user {request.user_id}")
            
            # Get user profile
            user_profile = self._get_user_profile(request.user_id)
            if not user_profile:
                raise ValueError(f"User profile {request.user_id} not found")
            
            # Get candidate travelers
            candidate_travelers = self._get_candidate_travelers(request)
            
            # Calculate compatibility scores
            scored_matches = self._calculate_compatibility_scores(
                user_profile, 
                candidate_travelers, 
                request
            )
            
            # Apply filtering and ranking
            final_matches = self._apply_matching_filters(
                scored_matches, 
                request.max_matches
            )
            
            response = MatchingResponse(
                matches=final_matches,
                user_id=request.user_id,
                generated_at=datetime.now(timezone.utc),
                total_matches=len(final_matches),
                search_criteria={
                    'location': request.location.dict(),
                    'travel_dates': request.travel_dates,
                    'preferences': [pref.value for pref in request.preferences] if request.preferences else []
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error finding travel partners: {str(e)}")
            raise
    
    async def calculate_compatibility(self, user_id: str, target_user_id: str) -> Optional[Dict[str, Any]]:
        """Returns a multidimensional compatibility breakdown plus ML blend.

        Args:
            user_id: First traveler.
            target_user_id: Second traveler.

        Returns:
            Analysis dict with overall score, dimensions, weights, and reasons,
            or ``None`` if either profile is missing or on error.
        """
        try:
            logger.info("Calculating compatibility between two users")
            
            # Get user profiles
            user_profile = self._get_user_profile(user_id)
            target_profile = self._get_user_profile(target_user_id)
            
            if not user_profile or not target_profile:
                return None
            
            # PBI 26: multidimensional scores (interests, estilo, presupuesto, ritmo, personalidad)
            dimensions = self._compute_match_dimensions(user_profile, target_profile)
            weights = self.learning_store.get_weights()
            overall_score = sum(
                dimensions.get(dim, 0.0) * weights.get(dim, 0.0) for dim in weights
            )
            overall_score = min(1.0, max(0.0, overall_score))

            preference_compatibility = self._calculate_preference_compatibility(
                user_profile.get('preferences', []),
                target_profile.get('preferences', []),
            )
            travel_style_compatibility = self._calculate_travel_style_compatibility(
                user_profile, target_profile
            )
            demographic_compatibility = self._calculate_demographic_compatibility(
                user_profile, target_profile
            )

            ml_signal = await self._matching_model_signal(user_profile, target_profile, dimensions)

            compatibility_analysis = {
                'user_id': user_id,
                'target_user_id': target_user_id,
                'overall_score': min(0.7 * overall_score + 0.3 * ml_signal, 1.0),
                'dimensions': dimensions,
                'weights_used': weights,
                'preference_compatibility': preference_compatibility,
                'travel_style_compatibility': travel_style_compatibility,
                'demographic_compatibility': demographic_compatibility,
                'common_preferences': preference_compatibility['common_preferences'],
                'recommendation_reason': self._generate_multidimensional_explanation(
                    dimensions, weights
                ),
                'calculated_at': datetime.now(timezone.utc),
            }
            
            return compatibility_analysis
            
        except Exception as e:
            logger.error(f"Error calculating compatibility: {str(e)}")
            return None
    
    def initiate_connection(self, user_id: str, target_user_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Creates a pending connection record with timestamps.

        Args:
            user_id: Initiator.
            target_user_id: Recipient.
            message: Optional opener text.

        Returns:
            Connection document including generated ``connection_id``.

        Raises:
            Exception: Logged and re-raised on persistence failures.
        """
        try:
            logger.info("Initiating user connection")
            
            connection_id = f"conn_{user_id}_{target_user_id}_{datetime.now(timezone.utc).timestamp()}"
            
            connection = {
                'connection_id': connection_id,
                'initiator_id': user_id,
                'target_user_id': target_user_id,
                'message': message,
                'status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'updated_at': datetime.now(timezone.utc)
            }
            
            with self._db() as db:
                db.add(
                    MatchingConnectionRecord(
                        connection_id=connection_id,
                        initiator_id=user_id,
                        target_user_id=target_user_id,
                        message=message,
                        status="pending",
                        response_message=None,
                        created_at=connection["created_at"],
                        updated_at=connection["updated_at"],
                    )
                )
                db.commit()
            
            return connection
            
        except Exception as e:
            logger.error(f"Error initiating connection: {str(e)}")
            raise
    
    def get_user_connections(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists connections where the user is initiator or target, newest first.

        Args:
            user_id: Participant to filter on.
            status: Optional exact status match (e.g. ``pending``).

        Returns:
            Matching connection dicts, or empty list on error.
        """
        try:
            logger.info("Fetching user connections")
            
            with self._db() as db:
                rows = db.scalars(
                    select(MatchingConnectionRecord)
                    .where(
                        (MatchingConnectionRecord.initiator_id == user_id)
                        | (MatchingConnectionRecord.target_user_id == user_id)
                    )
                    .order_by(desc(MatchingConnectionRecord.created_at))
                ).all()
            out: List[Dict[str, Any]] = []
            for row in rows:
                if status and row.status != status:
                    continue
                out.append(
                    {
                        "connection_id": row.connection_id,
                        "initiator_id": row.initiator_id,
                        "target_user_id": row.target_user_id,
                        "message": row.message,
                        "status": row.status,
                        "response_message": row.response_message,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                    }
                )
            return out
            
        except Exception as e:
            logger.error(f"Error fetching connections: {str(e)}")
            return []
    
    def respond_to_connection(self, connection_id: str, response: str, message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Updates status and optional response message for a connection.

        Args:
            connection_id: Key in ``self.connections``.
            response: New status string (e.g. accept/decline).
            message: Optional reply body.

        Returns:
            Updated connection dict, or ``None`` if unknown or on error.
        """
        try:
            logger.info("Responding to user connection")
            
            with self._db() as db:
                row = db.get(MatchingConnectionRecord, connection_id)
                if not row:
                    return None
                row.status = response
                row.response_message = message
                row.updated_at = datetime.now(timezone.utc)
                db.commit()
                return {
                    "connection_id": row.connection_id,
                    "initiator_id": row.initiator_id,
                    "target_user_id": row.target_user_id,
                    "message": row.message,
                    "status": row.status,
                    "response_message": row.response_message,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            
        except Exception as e:
            logger.error(f"Error responding to connection: {str(e)}")
            return None
    
    def get_travel_buddy_recommendations(self, user_id: str, location: Optional[str] = None, limit: int = 10) -> List[TravelerMatch]:
        """Ranks ingested users by simple compatibility, optionally by location.

        Args:
            user_id: Seeker; excluded from results.
            location: If set, requires exact ``location`` string match.
            limit: Max buddies to return.

        Returns:
            Sorted ``TravelerMatch`` list, possibly empty if profile missing or on error.
        """
        try:
            logger.info("Getting travel buddy recommendations")
            
            # Get user profile
            user_profile = self._get_user_profile(user_id)
            if not user_profile:
                return []
            
            # Get all potential matches
            all_users = self._get_all_users()
            
            # Calculate compatibility scores
            recommendations = []
            for user_data in all_users:
                if user_data['user_id'] == user_id:
                    continue
                
                # Apply location filter if specified
                if location and user_data.get('location') != location:
                    continue
                
                compatibility = self._calculate_simple_compatibility(
                    user_profile, 
                    user_data
                )
                common_preferences = self._get_common_preferences(
                    user_profile.get('preferences', []),
                    user_data.get('preferences', []),
                )
                
                if compatibility >= settings.MIN_COMPATIBILITY_SCORE:
                    match = TravelerMatch(
                        user_id=user_data['user_id'],
                        name=user_data['name'],
                        age=user_data.get('age'),
                        compatibility_score=compatibility,
                        common_preferences=common_preferences,
                        travel_style_match=compatibility,
                        bio=user_data.get('bio'),
                        profile_image=user_data.get('profile_image')
                    )
                    recommendations.append(match)
            
            # Sort by compatibility score and limit results
            recommendations.sort(key=lambda x: x.compatibility_score, reverse=True)
            
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error getting travel buddy recommendations: {str(e)}")
            return []
    
    def record_match_feedback(self, user_id: str, target_user_id: str, rating: int, feedback_text: Optional[str] = None):
        """Logs qualitative feedback and nudges learned weights from numeric rating.

        Args:
            user_id: Rater.
            target_user_id: Other party in the match.
            rating: 1–5 score consumed by ``_update_matching_algorithm``.
            feedback_text: Optional free-text note.

        Raises:
            Exception: Propagates after logging on unexpected failures.
        """
        try:
            logger.info("Recording match feedback")
            
            # In production, store in database and use for model improvement
            _ = feedback_text
            logger.info("Match feedback recorded with rating %s", rating)
            
            # Update matching algorithms based on feedback
            self._update_matching_algorithm(user_id, target_user_id, rating)
            
        except Exception as e:
            logger.error(f"Error recording match feedback: {str(e)}")
            raise
    
    # Private helper methods
    
    def _get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Resolves a traveler dict from ingested profiles."""
        profile = self.user_profiles.get(user_id)
        if profile:
            return profile
        with self._db() as db:
            row = db.get(MatchingProfileRecord, user_id)
            if not row:
                return None
            parsed = json.loads(row.profile_json)
            self.user_profiles[user_id] = parsed
            return parsed
    
    def _get_candidate_travelers(self, request: TravelerMatchRequest) -> List[Dict[str, Any]]:
        """Returns ingested users except requester, with optional location filter."""
        all_users = self._get_all_users()
        
        # Filter out the requesting user
        candidates = [user for user in all_users if user['user_id'] != request.user_id]
        
        # Apply location filter
        if request.location:
            candidates = [user for user in candidates if user.get('location')]
        
        return candidates
    
    def _get_all_users(self) -> List[Dict[str, Any]]:
        """Full ingested roster used by buddy recommendations and candidate expansion."""
        with self._db() as db:
            rows = db.scalars(select(MatchingProfileRecord)).all()
        out: List[Dict[str, Any]] = []
        for row in rows:
            parsed = json.loads(row.profile_json)
            self.user_profiles[parsed["user_id"]] = parsed
            out.append(parsed)
        return out
    
    def _calculate_compatibility_scores(self, user_profile: Dict[str, Any], candidates: List[Dict[str, Any]], request: TravelerMatchRequest) -> List[Dict[str, Any]]:
        """Scores each candidate, boosts overlap with requested preferences, and attaches commons."""
        scored_candidates = []
        
        for candidate in candidates:
            compatibility_score = self._calculate_simple_compatibility(user_profile, candidate)
            if request.preferences:
                req_p = {p.value for p in request.preferences}
                cand_p = {getattr(p, "value", str(p)) for p in candidate.get("preferences", [])}
                if req_p & cand_p:
                    compatibility_score = min(1.0, compatibility_score + 0.06)

            candidate_data = candidate.copy()
            candidate_data['compatibility_score'] = compatibility_score
            candidate_data['common_preferences'] = self._get_common_preferences(
                user_profile.get('preferences', []), 
                candidate.get('preferences', [])
            )
            
            scored_candidates.append(candidate_data)
        
        return scored_candidates
    
    def _calculate_simple_compatibility(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> float:
        """Weighted sum of PBI 26 dimensions using ``learning_store`` weights (clamped to 1.0)."""
        dimensions = self._compute_match_dimensions(user1, user2)
        weights = self.learning_store.get_weights()
        return min(
            1.0,
            sum(dimensions.get(k, 0.0) * weights.get(k, 0.0) for k in weights),
        )
    
    def _get_common_preferences(self, prefs1: List[TravelPreference], prefs2: List[TravelPreference]) -> List[TravelPreference]:
        """Intersection of two preference lists as a stable list."""
        set1 = set(prefs1)
        set2 = set(prefs2)
        return list(set1.intersection(set2))
    
    def _apply_matching_filters(self, scored_candidates: List[Dict[str, Any]], max_matches: int) -> List[TravelerMatch]:
        """Drops below-threshold scores, sorts descending, and maps to ``TravelerMatch``."""
        # Filter by minimum compatibility score
        filtered_candidates = [
            candidate for candidate in scored_candidates
            if candidate['compatibility_score'] >= settings.MIN_COMPATIBILITY_SCORE
        ]
        
        # Sort by compatibility score
        filtered_candidates.sort(key=lambda x: x['compatibility_score'], reverse=True)
        
        # Convert to TravelerMatch objects
        matches = []
        for candidate in filtered_candidates[:max_matches]:
            match = TravelerMatch(
                user_id=candidate['user_id'],
                name=candidate['name'],
                age=candidate.get('age'),
                compatibility_score=candidate['compatibility_score'],
                common_preferences=candidate.get('common_preferences', []),
                travel_style_match=candidate['compatibility_score'],  # Simplified
                bio=candidate.get('bio'),
                profile_image=candidate.get('profile_image')
            )
            matches.append(match)
        
        return matches
    
    def _calculate_preference_compatibility(self, prefs1: List[TravelPreference], prefs2: List[TravelPreference]) -> Dict[str, Any]:
        """Jaccard-style overlap on enumerated travel preferences."""
        set1 = set(prefs1)
        set2 = set(prefs2)
        
        if not set1 or not set2:
            return {'score': 0.0, 'common_preferences': []}
        
        common = list(set1.intersection(set2))
        score = len(common) / len(set1.union(set2))
        
        return {
            'score': score,
            'common_preferences': common,
            'total_common': len(common),
            'total_unique': len(set1.union(set2))
        }
    
    def _calculate_travel_style_compatibility(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> Dict[str, Any]:
        """Binary style match (1.0 equal, 0.5 otherwise) with echo fields."""
        style1 = user1.get('travel_style', '')
        style2 = user2.get('travel_style', '')
        
        score = 1.0 if style1 == style2 else 0.5
        
        return {
            'score': score,
            'user1_style': style1,
            'user2_style': style2,
            'style_match': style1 == style2
        }
    
    def _calculate_demographic_compatibility(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> Dict[str, Any]:
        """Age-gap heuristic mapped to a 0–1 compatibility score."""
        age1 = user1.get('age', 0)
        age2 = user2.get('age', 0)
        
        age_score = 0.0
        if age1 and age2:
            age_diff = abs(age1 - age2)
            if age_diff <= 5:
                age_score = 1.0
            elif age_diff <= 10:
                age_score = 0.7
            elif age_diff <= 15:
                age_score = 0.4
            else:
                age_score = 0.1
        
        return {
            'score': age_score,
            'age_difference': abs(age1 - age2) if age1 and age2 else 0,
            'age_compatibility': age_score
        }
    
    def _generate_multidimensional_explanation(
        self, dimensions: Dict[str, float], weights: Dict[str, float]
    ) -> str:
        """Ranks dimensions by weighted score and returns a short Spanish summary string."""
        ranked = sorted(dimensions.items(), key=lambda kv: kv[1] * weights.get(kv[0], 0), reverse=True)
        top = [f"{name} ({score:.0%})" for name, score in ranked[:3] if score > 0.35]
        if not top:
            return "Compatibilidad moderada en varias dimensiones."
        return "Mayor alineación en: " + ", ".join(top)

    def _compute_match_dimensions(
        self, user_a: Dict[str, Any], user_b: Dict[str, Any]
    ) -> Dict[str, float]:
        """PBI 26: per-dimension 0–1 signals (interests, style, budget, pace, personality)."""
        prefs_a = {getattr(p, "value", str(p)) for p in user_a.get("preferences", [])}
        prefs_b = {getattr(p, "value", str(p)) for p in user_b.get("preferences", [])}
        union = prefs_a | prefs_b
        interests = len(prefs_a & prefs_b) / len(union) if union else 0.55

        style_a = user_a.get("travel_style", "")
        style_b = user_b.get("travel_style", "")
        travel_style = 1.0 if style_a and style_a == style_b else 0.4

        tier_a = user_a.get("budget_tier", "mid")
        tier_b = user_b.get("budget_tier", "mid")
        budget = 1.0 if tier_a == tier_b else 0.45

        pace_a = user_a.get("pace", "moderate")
        pace_b = user_b.get("pace", "moderate")
        pace = 1.0 if pace_a == pace_b else 0.42

        tags_a = set(user_a.get("personality_tags", []))
        tags_b = set(user_b.get("personality_tags", []))
        u_tags = tags_a | tags_b
        personality = len(tags_a & tags_b) / len(u_tags) if u_tags else 0.5

        return {
            "interests": round(float(interests), 4),
            "travel_style": round(float(travel_style), 4),
            "budget": round(float(budget), 4),
            "pace": round(float(pace), 4),
            "personality": round(float(personality), 4),
        }

    async def _matching_model_signal(
        self,
        user_profile: Dict[str, Any],
        target_profile: Dict[str, Any],
        dimensions: Dict[str, float],
    ) -> float:
        """Uses ``traveler_matching_model`` when loaded; otherwise averages dimension scores."""
        model = self.model_manager.get_model("traveler_matching_model")
        if not model or not model.is_loaded:
            return float(sum(dimensions.values()) / max(len(dimensions), 1))
        try:
            pred = await model.predict(
                {
                    "user1_id": user_profile.get("user_id", ""),
                    "user2_id": target_profile.get("user_id", ""),
                    "user1_profile": {"preferences": [p.value for p in user_profile.get("preferences", [])]},
                    "user2_profile": {"preferences": [p.value for p in target_profile.get("preferences", [])]},
                }
            )
            return float(min(1.0, max(0.0, pred.get("compatibility_score", 0.75))))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Matching model signal fallback: %s", exc)
            return float(sum(dimensions.values()) / max(len(dimensions), 1))

    def process_connection_outcome(
        self,
        user_id: str,
        target_user_id: str,
        outcome: ConnectionOutcome,
        dimension_snapshot: Optional[Dict[str, float]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, float]:
        """PBI 27: records success/incompatibility against optional dimension snapshot."""
        snap = dimension_snapshot
        if snap is None:
            ua = self._get_user_profile(user_id)
            ub = self._get_user_profile(target_user_id)
            if ua and ub:
                snap = self._compute_match_dimensions(ua, ub)
            else:
                snap = {}
        if outcome == ConnectionOutcome.SUCCESS:
            return self.learning_store.record_success(snap, notes)
        return self.learning_store.record_incompatible(snap, notes)

    def _update_matching_algorithm(self, user_id: str, target_user_id: str, rating: int):
        """Delegates rating-side learning to ``learning_store.record_rating_feedback``."""
        _ = (user_id, target_user_id)
        self.learning_store.record_rating_feedback(rating)
        logger.info(
            "Updated matching weights from rating %s/5",
            rating,
        )
