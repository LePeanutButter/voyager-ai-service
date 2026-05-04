"""
Recommendation service for personalized travel suggestions.

Implements the core recommendation logic using ML models and
business rules for generating personalized travel recommendations.
"""

from typing import List, Dict, Any, Optional
import logging
import random
from datetime import datetime, timedelta, timezone

from app.models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    Activity,
    Location,
    ActivityType,
    TravelPreference
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating personalized travel recommendations."""
    
    def __init__(self, model_manager):
        """Initialize with ML model manager."""
        self.model_manager = model_manager
        self.cache = {}  # Simple in-memory cache (replace with Redis in production)
    
    async def generate_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        Generate personalized recommendations based on user profile and context.
        
        Args:
            request: Recommendation request with user context and preferences
            
        Returns:
            RecommendationResponse with personalized activities and confidence scores
        """
        try:
            logger.info(f"Generating recommendations for user {request.user_id}")
            
            # Get user profile for personalization
            user_profile = await self._get_user_profile(request.user_id)
            
            # Get candidate activities based on location and filters
            candidate_activities = await self._get_candidate_activities(request)
            
            # Score activities using ML models and business rules
            scored_activities = await self._score_activities(
                candidate_activities, 
                user_profile, 
                request
            )
            
            # Apply diversity and ranking algorithms
            final_recommendations = await self._apply_ranking_and_diversity(
                scored_activities, 
                request.max_results
            )
            
            # Generate explanation for recommendations
            explanation = await self._generate_explanation(
                final_recommendations, 
                user_profile
            )
            
            response = RecommendationResponse(
                recommendations=final_recommendations,
                user_id=request.user_id,
                generated_at=datetime.now(timezone.utc),
                total_results=len(final_recommendations),
                confidence_scores=[act.get('confidence_score', 0.0) for act in final_recommendations],
                explanation=explanation
            )
            
            # Cache the response for future requests
            cache_key = f"rec_{request.user_id}_{hash(str(request.location))}"
            self.cache[cache_key] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            raise
    
    async def get_popular_activities(self, location: str, limit: int) -> List[Activity]:
        """
        Get popular activities for a specific location.
        
        Args:
            location: Location name
            limit: Maximum number of activities to return
            
        Returns:
            List of popular activities
        """
        try:
            # Mock implementation - in production, query database
            mock_activities = await self._generate_mock_activities(location, limit)
            
            # Sort by rating and popularity
            popular_activities = sorted(
                mock_activities, 
                key=lambda x: (x.rating, random.random()), 
                reverse=True
            )[:limit]
            
            return popular_activities
            
        except Exception as e:
            logger.error(f"Error fetching popular activities: {str(e)}")
            raise
    
    async def get_trending_activities(self, category: Optional[str], limit: int) -> List[Activity]:
        """
        Get trending activities globally or by category.
        
        Args:
            category: Optional activity category filter
            limit: Maximum number of activities to return
            
        Returns:
            List of trending activities
        """
        try:
            # Mock implementation - in production, analyze recent interactions
            mock_activities = await self._generate_mock_activities("global", limit * 2)
            
            # Filter by category if specified
            if category:
                mock_activities = [
                    act for act in mock_activities 
                    if act.category.value.lower() == category.lower()
                ]
            
            # Simulate trending with random boost and recency
            trending_activities = []
            for activity in mock_activities:
                trending_score = activity.rating + random.uniform(0, 1)
                activity_dict = activity.dict()
                activity_dict['trending_score'] = trending_score
                trending_activities.append(activity_dict)
            
            # Sort by trending score
            trending_activities.sort(key=lambda x: x['trending_score'], reverse=True)
            
            return [Activity(**act) for act in trending_activities[:limit]]
            
        except Exception as e:
            logger.error(f"Error fetching trending activities: {str(e)}")
            raise
    
    async def get_similar_activities(self, activity_id: str, limit: int) -> List[Activity]:
        """
        Get activities similar to a specific activity.
        
        Args:
            activity_id: Reference activity ID
            limit: Maximum number of similar activities
            
        Returns:
            List of similar activities
        """
        try:
            # Get reference activity (mock implementation)
            reference_activity = await self._get_activity_by_id(activity_id)
            if not reference_activity:
                return []
            
            # Get candidate activities
            all_activities = await self._generate_mock_activities("similar", limit * 3)
            
            # Calculate similarity scores
            similar_activities = []
            for activity in all_activities:
                if activity.activity_id == activity_id:
                    continue
                
                similarity_score = await self._calculate_similarity(
                    reference_activity, 
                    activity
                )
                
                activity_dict = activity.dict()
                activity_dict['similarity_score'] = similarity_score
                similar_activities.append(activity_dict)
            
            # Sort by similarity and return top matches
            similar_activities.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return [Activity(**act) for act in similar_activities[:limit]]
            
        except Exception as e:
            logger.error(f"Error fetching similar activities: {str(e)}")
            raise
    
    async def record_feedback(self, user_id: str, activity_id: str, rating: int, feedback_text: Optional[str]):
        """
        Record user feedback for recommendations.
        
        Args:
            user_id: User identifier
            activity_id: Activity identifier
            rating: Rating from 1-5
            feedback_text: Optional detailed feedback
        """
        try:
            # In production, store in database and use for model retraining
            feedback_data = {
                'user_id': user_id,
                'activity_id': activity_id,
                'rating': rating,
                'feedback_text': feedback_text,
                'timestamp': datetime.now(timezone.utc)
            }
            
            logger.info(f"Recorded feedback: {feedback_data}")
            
            # Update user preferences based on feedback
            await self._update_user_preferences_from_feedback(user_id, activity_id, rating)
            
        except Exception as e:
            logger.error(f"Error recording feedback: {str(e)}")
            raise
    
    async def get_activity_categories(self) -> List[str]:
        """
        Get all available activity categories.
        
        Returns:
            List of activity category names
        """
        return [category.value for category in ActivityType]
    
    # Private helper methods
    
    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile for personalization."""
        # Mock implementation - in production, query database
        return {
            'user_id': user_id,
            'preferences': [TravelPreference.CULTURAL, TravelPreference.FOODIE],
            'travel_history': [],
            'location': 'New York',
            'budget_range': {'min': 50, 'max': 200}
        }
    
    async def _get_candidate_activities(self, request: RecommendationRequest) -> List[Activity]:
        """Get candidate activities based on location and filters."""
        # Mock implementation - in production, query database with location filters
        return await self._generate_mock_activities(request.location.city or "Unknown", request.max_results * 3)
    
    async def _score_activities(self, activities: List[Activity], user_profile: Dict[str, Any], request: RecommendationRequest) -> List[Dict[str, Any]]:
        """Score activities based on user preferences and context."""
        scored_activities = []
        
        for activity in activities:
            score = 0.0
            
            # Base score from rating
            score += activity.rating * 0.3
            
            # Preference matching
            user_preferences = user_profile.get('preferences', [])
            for pref in user_preferences:
                if pref.value in [tag.lower() for tag in activity.tags]:
                    score += 0.4
            
            # Location proximity (mock calculation)
            score += random.uniform(0.1, 0.3) * 0.2
            
            # Price range matching
            budget = user_profile.get('budget_range', {})
            if budget:
                # Simple price matching logic
                score += random.uniform(0.1, 0.2) * 0.1
            
            activity_dict = activity.dict()
            activity_dict['confidence_score'] = min(score, 1.0)
            scored_activities.append(activity_dict)
        
        return scored_activities
    
    async def _apply_ranking_and_diversity(self, scored_activities: List[Dict[str, Any]], max_results: int) -> List[Activity]:
        """Apply ranking and diversity algorithms to final recommendations."""
        # Sort by confidence score
        scored_activities.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Apply diversity - ensure different categories are represented
        diverse_recommendations = []
        category_counts = {}
        
        for activity in scored_activities:
            category = activity['category']
            if category not in category_counts:
                category_counts[category] = 0
            
            # Limit activities per category for diversity
            if category_counts[category] < max(2, max_results // 3):
                diverse_recommendations.append(Activity(**activity))
                category_counts[category] += 1
                
                if len(diverse_recommendations) >= max_results:
                    break
        
        return diverse_recommendations
    
    async def _generate_explanation(self, recommendations: List[Activity], user_profile: Dict[str, Any]) -> str:
        """Generate explanation for recommendations."""
        if not recommendations:
            return "No recommendations available at the moment."
        
        categories = list(set([rec.category.value for rec in recommendations]))
        user_prefs = [pref.value for pref in user_profile.get('preferences', [])]
        
        explanation = f"Based on your interest in {', '.join(user_prefs[:3])}, "
        explanation += f"I recommend these {', '.join(categories[:3])} activities. "
        explanation += f"These match your preferences and have high ratings from similar travelers."
        
        return explanation
    
    async def _generate_mock_activities(self, location: str, count: int) -> List[Activity]:
        """Generate mock activities for testing."""
        activities = []
        categories = list(ActivityType)
        preferences = list(TravelPreference)
        
        for i in range(count):
            activity = Activity(
                activity_id=f"activity_{location}_{i}",
                name=f"Activity {i+1} in {location}",
                category=random.choice(categories),
                description=f"Amazing activity {i+1} in {location} with great experiences",
                location=Location(
                    latitude=random.uniform(-90, 90),
                    longitude=random.uniform(-180, 180),
                    city=location,
                    country="Country",
                    radius_km=10.0
                ),
                rating=random.uniform(3.0, 5.0),
                price_range=random.choice(["$", "$$", "$$$", "$$$$"]),
                duration_hours=random.uniform(1, 8),
                tags=[random.choice([pref.value for pref in preferences]) for _ in range(3)],
                requirements=[],
                best_time_to_visit="Any time",
                images=[]
            )
            activities.append(activity)
        
        return activities
    
    async def _get_activity_by_id(self, activity_id: str) -> Optional[Activity]:
        """Get activity by ID (mock implementation)."""
        # Mock implementation - in production, query database
        activities = await self._generate_mock_activities("test", 100)
        for activity in activities:
            if activity.activity_id == activity_id:
                return activity
        return None
    
    async def _calculate_similarity(self, activity1: Activity, activity2: Activity) -> float:
        """Calculate similarity between two activities."""
        similarity = 0.0
        
        # Category similarity
        if activity1.category == activity2.category:
            similarity += 0.4
        
        # Tag similarity
        tags1 = set(activity1.tags)
        tags2 = set(activity2.tags)
        if tags1 and tags2:
            tag_similarity = len(tags1.intersection(tags2)) / len(tags1.union(tags2))
            similarity += tag_similarity * 0.3
        
        # Price range similarity
        if activity1.price_range == activity2.price_range:
            similarity += 0.2
        
        # Rating similarity
        rating_diff = abs(activity1.rating - activity2.rating)
        rating_similarity = 1 - (rating_diff / 5.0)
        similarity += rating_similarity * 0.1
        
        return min(similarity, 1.0)
    
    async def _update_user_preferences_from_feedback(self, user_id: str, activity_id: str, rating: int):
        """Update user preferences based on feedback."""
        # In production, implement preference learning algorithm
        logger.info(f"Updating preferences for user {user_id} based on feedback for {activity_id}")
