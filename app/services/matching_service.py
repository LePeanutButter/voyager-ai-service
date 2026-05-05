"""
Traveler matching service for finding compatible travel partners.

Implements compatibility algorithms and connection management
for matching travelers with similar interests and preferences.
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta, timezone

from app.models.schemas import (
    TravelerMatchRequest,
    TravelerMatch,
    MatchingResponse,
    TravelPreference,
    ConnectionOutcome,
)
from app.core.config import settings
from app.ml.learning_store import MatchingLearningStore

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for finding compatible travel partners."""
    
    def __init__(self, model_manager, learning_store: MatchingLearningStore):
        """Initialize with ML model manager and continuous-learning store (PBI 27)."""
        self.model_manager = model_manager
        self.learning_store = learning_store
        self.connections = {}  # In-memory storage (replace with database in production)
        self.user_profiles = {}  # Mock user profiles for matching
    
    async def find_travel_partners(self, request: TravelerMatchRequest) -> MatchingResponse:
        """
        Find compatible travel partners based on preferences and context.
        
        Args:
            request: Traveler matching request with preferences and criteria
            
        Returns:
            MatchingResponse with compatible travelers and compatibility scores
        """
        try:
            logger.info(f"Finding travel partners for user {request.user_id}")
            
            # Get user profile
            user_profile = await self._get_user_profile(request.user_id)
            if not user_profile:
                raise ValueError(f"User profile {request.user_id} not found")
            
            # Get candidate travelers
            candidate_travelers = await self._get_candidate_travelers(request)
            
            # Calculate compatibility scores
            scored_matches = await self._calculate_compatibility_scores(
                user_profile, 
                candidate_travelers, 
                request
            )
            
            # Apply filtering and ranking
            final_matches = await self._apply_matching_filters(
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
        """
        Calculate detailed compatibility between two users.
        
        Args:
            user_id: First user identifier
            target_user_id: Second user identifier
            
        Returns:
            Detailed compatibility analysis or None if users not found
        """
        try:
            logger.info(f"Calculating compatibility between {user_id} and {target_user_id}")
            
            # Get user profiles
            user_profile = await self._get_user_profile(user_id)
            target_profile = await self._get_user_profile(target_user_id)
            
            if not user_profile or not target_profile:
                return None
            
            # PBI 26: multidimensional scores (interests, estilo, presupuesto, ritmo, personalidad)
            dimensions = await self._compute_match_dimensions(user_profile, target_profile)
            weights = self.learning_store.get_weights()
            overall_score = sum(
                dimensions.get(dim, 0.0) * weights.get(dim, 0.0) for dim in weights
            )
            overall_score = min(1.0, max(0.0, overall_score))

            preference_compatibility = await self._calculate_preference_compatibility(
                user_profile.get('preferences', []),
                target_profile.get('preferences', []),
            )
            travel_style_compatibility = await self._calculate_travel_style_compatibility(
                user_profile, target_profile
            )
            demographic_compatibility = await self._calculate_demographic_compatibility(
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
                'recommendation_reason': await self._generate_multidimensional_explanation(
                    dimensions, weights
                ),
                'calculated_at': datetime.now(timezone.utc),
            }
            
            return compatibility_analysis
            
        except Exception as e:
            logger.error(f"Error calculating compatibility: {str(e)}")
            return None
    
    async def initiate_connection(self, user_id: str, target_user_id: str, message: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiate connection with a matched traveler.
        
        Args:
            user_id: User initiating the connection
            target_user_id: Target user
            message: Optional connection message
            
        Returns:
            Connection details
        """
        try:
            logger.info(f"Initiating connection from {user_id} to {target_user_id}")
            
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
            
            # Store connection
            if connection_id not in self.connections:
                self.connections[connection_id] = connection
            
            return connection
            
        except Exception as e:
            logger.error(f"Error initiating connection: {str(e)}")
            raise
    
    async def get_user_connections(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get user's connections and connection requests.
        
        Args:
            user_id: User identifier
            status: Optional status filter (pending, accepted, declined)
            
        Returns:
            List of connections
        """
        try:
            logger.info(f"Fetching connections for user {user_id}")
            
            user_connections = []
            
            for connection in self.connections.values():
                if (connection['initiator_id'] == user_id or 
                    connection['target_user_id'] == user_id):
                    
                    if status is None or connection['status'] == status:
                        user_connections.append(connection)
            
            # Sort by creation date (newest first)
            user_connections.sort(key=lambda x: x['created_at'], reverse=True)
            
            return user_connections
            
        except Exception as e:
            logger.error(f"Error fetching connections: {str(e)}")
            return []
    
    async def respond_to_connection(self, connection_id: str, response: str, message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Respond to a connection request.
        
        Args:
            connection_id: Connection identifier
            response: Response type (accept, decline)
            message: Optional response message
            
        Returns:
            Updated connection or None if not found
        """
        try:
            logger.info(f"Responding to connection {connection_id} with {response}")
            
            connection = self.connections.get(connection_id)
            if not connection:
                return None
            
            # Update connection
            connection['status'] = response
            connection['response_message'] = message
            connection['updated_at'] = datetime.now(timezone.utc)
            
            self.connections[connection_id] = connection
            
            return connection
            
        except Exception as e:
            logger.error(f"Error responding to connection: {str(e)}")
            return None
    
    async def get_travel_buddy_recommendations(self, user_id: str, location: Optional[str] = None, limit: int = 10) -> List[TravelerMatch]:
        """
        Get travel buddy recommendations based on user preferences.
        
        Args:
            user_id: User identifier
            location: Optional location filter
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended travel buddies
        """
        try:
            logger.info(f"Getting travel buddy recommendations for user {user_id}")
            
            # Get user profile
            user_profile = await self._get_user_profile(user_id)
            if not user_profile:
                return []
            
            # Get all potential matches
            all_users = await self._get_all_users()
            
            # Calculate compatibility scores
            recommendations = []
            for user_data in all_users:
                if user_data['user_id'] == user_id:
                    continue
                
                # Apply location filter if specified
                if location and user_data.get('location') != location:
                    continue
                
                compatibility = await self._calculate_simple_compatibility(
                    user_profile, 
                    user_data
                )
                
                if compatibility >= settings.MIN_COMPATIBILITY_SCORE:
                    match = TravelerMatch(
                        user_id=user_data['user_id'],
                        name=user_data['name'],
                        age=user_data.get('age'),
                        compatibility_score=compatibility,
                        common_preferences=user_data.get('common_preferences', []),
                        travel_style_match=compatibility,  # Simplified for demo
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
    
    async def record_match_feedback(self, user_id: str, target_user_id: str, rating: int, feedback_text: Optional[str] = None):
        """
        Record feedback for a travel match.
        
        Args:
            user_id: User identifier
            target_user_id: Matched user identifier
            rating: Rating from 1-5
            feedback_text: Optional detailed feedback
        """
        try:
            logger.info(f"Recording match feedback from {user_id} for {target_user_id}")
            
            feedback_data = {
                'user_id': user_id,
                'target_user_id': target_user_id,
                'rating': rating,
                'feedback_text': feedback_text,
                'timestamp': datetime.now(timezone.utc)
            }
            
            # In production, store in database and use for model improvement
            logger.info(f"Match feedback recorded: {feedback_data}")
            
            # Update matching algorithms based on feedback
            await self._update_matching_algorithm(user_id, target_user_id, rating)
            
        except Exception as e:
            logger.error(f"Error recording match feedback: {str(e)}")
            raise
    
    # Private helper methods
    
    async def _get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile for matching."""
        # Mock implementation - in production, query database
        mock_profiles = {
            'user1': {
                'user_id': 'user1',
                'name': 'John Doe',
                'age': 28,
                'location': 'New York',
                'preferences': [TravelPreference.CULTURAL, TravelPreference.FOODIE],
                'travel_style': 'mid-range',
                'budget_tier': 'mid',
                'pace': 'moderate',
                'personality_tags': {'explorer', 'social', 'curious'},
                'bio': 'Love exploring new cultures and trying local cuisine',
            },
            'user2': {
                'user_id': 'user2',
                'name': 'Jane Smith',
                'age': 32,
                'location': 'San Francisco',
                'preferences': [TravelPreference.ADVENTURE, TravelPreference.NATURE],
                'travel_style': 'budget',
                'budget_tier': 'low',
                'pace': 'intense',
                'personality_tags': {'explorer', 'calm'},
                'bio': 'Adventure seeker who loves hiking and outdoor activities',
            },
            'user3': {
                'user_id': 'user3',
                'name': 'Mike Johnson',
                'age': 25,
                'location': 'Chicago',
                'preferences': [TravelPreference.RELAXATION, TravelPreference.BEACH],
                'travel_style': 'luxury',
                'budget_tier': 'high',
                'pace': 'relaxed',
                'personality_tags': {'social', 'curious', 'foodie'},
                'bio': 'Enjoy relaxing beach vacations and luxury travel',
            },
        }
        
        return mock_profiles.get(user_id)
    
    async def _get_candidate_travelers(self, request: TravelerMatchRequest) -> List[Dict[str, Any]]:
        """Get candidate travelers for matching."""
        # Mock implementation - in production, query database with filters
        all_users = await self._get_all_users()
        
        # Filter out the requesting user
        candidates = [user for user in all_users if user['user_id'] != request.user_id]
        
        # Apply location filter (mock)
        if request.location:
            candidates = [user for user in candidates if user.get('location')]
        
        return candidates
    
    async def _get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users for matching (mock implementation)."""
        return [
            {
                'user_id': 'user1',
                'name': 'John Doe',
                'age': 28,
                'location': 'New York',
                'preferences': [TravelPreference.CULTURAL, TravelPreference.FOODIE],
                'travel_style': 'mid-range',
                'budget_tier': 'mid',
                'pace': 'moderate',
                'personality_tags': {'explorer', 'social', 'curious'},
                'bio': 'Love exploring new cultures and trying local cuisine',
                'profile_image': None,
            },
            {
                'user_id': 'user2',
                'name': 'Jane Smith',
                'age': 32,
                'location': 'San Francisco',
                'preferences': [TravelPreference.ADVENTURE, TravelPreference.NATURE],
                'travel_style': 'budget',
                'budget_tier': 'low',
                'pace': 'intense',
                'personality_tags': {'explorer', 'calm'},
                'bio': 'Adventure seeker who loves hiking and outdoor activities',
                'profile_image': None,
            },
            {
                'user_id': 'user3',
                'name': 'Mike Johnson',
                'age': 25,
                'location': 'Chicago',
                'preferences': [TravelPreference.RELAXATION, TravelPreference.BEACH],
                'travel_style': 'luxury',
                'budget_tier': 'high',
                'pace': 'relaxed',
                'personality_tags': {'social', 'curious', 'foodie'},
                'bio': 'Enjoy relaxing beach vacations and luxury travel',
                'profile_image': None,
            },
        ]
    
    async def _calculate_compatibility_scores(self, user_profile: Dict[str, Any], candidates: List[Dict[str, Any]], request: TravelerMatchRequest) -> List[Dict[str, Any]]:
        """Calculate compatibility scores for all candidates."""
        scored_candidates = []
        
        for candidate in candidates:
            compatibility_score = await self._calculate_simple_compatibility(user_profile, candidate)
            if request.preferences:
                req_p = {p.value for p in request.preferences}
                cand_p = {p.value for p in candidate.get("preferences", [])}
                if req_p & cand_p:
                    compatibility_score = min(1.0, compatibility_score + 0.06)

            candidate_data = candidate.copy()
            candidate_data['compatibility_score'] = compatibility_score
            candidate_data['common_preferences'] = await self._get_common_preferences(
                user_profile.get('preferences', []), 
                candidate.get('preferences', [])
            )
            
            scored_candidates.append(candidate_data)
        
        return scored_candidates
    
    async def _calculate_simple_compatibility(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> float:
        """Aggregate compatibility using learned weights over multidimensional scores (PBI 26/27)."""
        dimensions = await self._compute_match_dimensions(user1, user2)
        weights = self.learning_store.get_weights()
        return min(
            1.0,
            sum(dimensions.get(k, 0.0) * weights.get(k, 0.0) for k in weights),
        )
    
    async def _get_common_preferences(self, prefs1: List[TravelPreference], prefs2: List[TravelPreference]) -> List[TravelPreference]:
        """Get common preferences between two users."""
        set1 = set(prefs1)
        set2 = set(prefs2)
        return list(set1.intersection(set2))
    
    async def _apply_matching_filters(self, scored_candidates: List[Dict[str, Any]], max_matches: int) -> List[TravelerMatch]:
        """Apply filters and ranking to final matches."""
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
    
    async def _calculate_preference_compatibility(self, prefs1: List[TravelPreference], prefs2: List[TravelPreference]) -> Dict[str, Any]:
        """Calculate preference compatibility."""
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
    
    async def _calculate_travel_style_compatibility(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate travel style compatibility."""
        style1 = user1.get('travel_style', '')
        style2 = user2.get('travel_style', '')
        
        score = 1.0 if style1 == style2 else 0.5
        
        return {
            'score': score,
            'user1_style': style1,
            'user2_style': style2,
            'style_match': style1 == style2
        }
    
    async def _calculate_demographic_compatibility(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate demographic compatibility."""
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
    
    async def _generate_multidimensional_explanation(
        self, dimensions: Dict[str, float], weights: Dict[str, float]
    ) -> str:
        """Human-readable rationale from dimension scores."""
        ranked = sorted(dimensions.items(), key=lambda kv: kv[1] * weights.get(kv[0], 0), reverse=True)
        top = [f"{name} ({score:.0%})" for name, score in ranked[:3] if score > 0.35]
        if not top:
            return "Compatibilidad moderada en varias dimensiones."
        return "Mayor alineación en: " + ", ".join(top)

    async def _compute_match_dimensions(
        self, user_a: Dict[str, Any], user_b: Dict[str, Any]
    ) -> Dict[str, float]:
        """PBI 26: interests, travel_style, budget, pace, personality (0–1 each)."""
        prefs_a = {p.value for p in user_a.get("preferences", [])}
        prefs_b = {p.value for p in user_b.get("preferences", [])}
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
        """Blend traveler matching model output when available (PBI 26)."""
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

    async def process_connection_outcome(
        self,
        user_id: str,
        target_user_id: str,
        outcome: ConnectionOutcome,
        dimension_snapshot: Optional[Dict[str, float]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, float]:
        """PBI 27: reinforce or dampen weights from explicit connection outcomes."""
        snap = dimension_snapshot
        if snap is None:
            ua = await self._get_user_profile(user_id)
            ub = await self._get_user_profile(target_user_id)
            if ua and ub:
                snap = await self._compute_match_dimensions(ua, ub)
            else:
                snap = {}
        if outcome == ConnectionOutcome.SUCCESS:
            return self.learning_store.record_success(snap, notes)
        return self.learning_store.record_incompatible(snap, notes)

    async def _update_matching_algorithm(self, user_id: str, target_user_id: str, rating: int):
        """Nudge learned weights from numeric feedback (PBI 27)."""
        self.learning_store.record_rating_feedback(rating)
        logger.info(
            "Updated matching weights from rating %s/5 (users %s <-> %s)",
            rating,
            user_id,
            target_user_id,
        )
