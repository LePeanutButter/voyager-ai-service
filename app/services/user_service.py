"""
User service for profile management and behavior analysis.

Handles user profile operations, preference learning, and
interaction tracking for personalized recommendations.
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

from app.models.schemas import (
    UserProfile,
    UserProfileUpdate,
    UserPreferences,
    UserInteraction,
    TravelPreference
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserService:
    """Service for user profile management and behavior analysis."""
    
    def __init__(self, model_manager):
        """Initialize with ML model manager."""
        self.model_manager = model_manager
        self.user_profiles = {}  # In-memory storage (replace with database in production)
        self.interactions = {}  # Store user interactions
    
    async def create_user_profile(self, profile: UserProfile) -> UserProfile:
        """
        Create a new user profile.
        
        Args:
            profile: User profile data
            
        Returns:
            Created user profile
        """
        try:
            logger.info(f"Creating profile for user {profile.user_id}")
            
            # Check if user already exists
            if profile.user_id in self.user_profiles:
                raise ValueError(f"User profile {profile.user_id} already exists")
            
            # Validate email format
            if '@' not in profile.email:
                raise ValueError("Invalid email format")
            
            # Analyze preferences using ML model
            analyzed_preferences = await self._analyze_preferences(profile.preferences)
            
            # Create enhanced profile
            enhanced_profile = UserProfile(
                user_id=profile.user_id,
                name=profile.name,
                email=profile.email,
                age=profile.age,
                location=profile.location,
                preferences=analyzed_preferences,
                travel_history=profile.travel_history,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Store profile
            self.user_profiles[profile.user_id] = enhanced_profile
            
            logger.info(f"Successfully created profile for user {profile.user_id}")
            return enhanced_profile
            
        except ValueError as e:
            logger.error(f"Validation error creating profile: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating user profile: {str(e)}")
            raise
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Get user profile by ID.
        
        Args:
            user_id: User identifier
            
        Returns:
            User profile or None if not found
        """
        try:
            return self.user_profiles.get(user_id)
        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}")
            return None
    
    async def update_user_profile(self, user_id: str, profile_update: UserProfileUpdate) -> Optional[UserProfile]:
        """
        Update user profile.
        
        Args:
            user_id: User identifier
            profile_update: Profile update data
            
        Returns:
            Updated user profile or None if not found
        """
        try:
            logger.info(f"Updating profile for user {user_id}")
            
            # Get existing profile
            existing_profile = self.user_profiles.get(user_id)
            if not existing_profile:
                return None
            
            # Update fields
            if profile_update.preferences:
                analyzed_preferences = await self._analyze_preferences(profile_update.preferences)
                existing_profile.preferences = analyzed_preferences
            
            if profile_update.location:
                existing_profile.location = profile_update.location
            
            if profile_update.travel_history:
                existing_profile.travel_history = profile_update.travel_history
            
            existing_profile.updated_at = datetime.utcnow()
            
            # Store updated profile
            self.user_profiles[user_id] = existing_profile
            
            logger.info(f"Successfully updated profile for user {user_id}")
            return existing_profile
            
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            return None
    
    async def update_user_preferences(self, user_id: str, preferences: UserPreferences) -> bool:
        """
        Update user preferences specifically.
        
        Args:
            user_id: User identifier
            preferences: New preferences
            
        Returns:
            True if successful, False if user not found
        """
        try:
            logger.info(f"Updating preferences for user {user_id}")
            
            # Get existing profile
            existing_profile = self.user_profiles.get(user_id)
            if not existing_profile:
                return False
            
            # Analyze and update preferences
            analyzed_preferences = await self._analyze_preferences(preferences)
            existing_profile.preferences = analyzed_preferences
            existing_profile.updated_at = datetime.utcnow()
            
            # Store updated profile
            self.user_profiles[user_id] = existing_profile
            
            logger.info(f"Successfully updated preferences for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {str(e)}")
            return False
    
    async def record_interaction(self, interaction: UserInteraction):
        """
        Record user interaction with recommendations.
        
        Args:
            interaction: User interaction data
        """
        try:
            logger.info(f"Recording interaction for user {interaction.user_id}")
            
            # Store interaction
            if interaction.user_id not in self.interactions:
                self.interactions[interaction.user_id] = []
            
            self.interactions[interaction.user_id].append(interaction)
            
            # Update user preferences based on interaction
            await self._update_preferences_from_interaction(interaction)
            
            # Limit interaction history
            max_interactions = 1000
            if len(self.interactions[interaction.user_id]) > max_interactions:
                self.interactions[interaction.user_id] = self.interactions[interaction.user_id][-max_interactions:]
            
        except Exception as e:
            logger.error(f"Error recording interaction: {str(e)}")
            raise
    
    async def get_interaction_history(self, user_id: str, limit: int) -> List[UserInteraction]:
        """
        Get user interaction history.
        
        Args:
            user_id: User identifier
            limit: Maximum number of interactions to return
            
        Returns:
            List of user interactions
        """
        try:
            user_interactions = self.interactions.get(user_id, [])
            return user_interactions[-limit:] if limit > 0 else user_interactions
        except Exception as e:
            logger.error(f"Error fetching interaction history: {str(e)}")
            return []
    
    async def generate_user_insights(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate user behavior insights and analytics.
        
        Args:
            user_id: User identifier
            
        Returns:
            User insights dictionary or None if user not found
        """
        try:
            logger.info(f"Generating insights for user {user_id}")
            
            # Get user profile
            profile = self.user_profiles.get(user_id)
            if not profile:
                return None
            
            # Get interaction history
            interactions = self.interactions.get(user_id, [])
            
            # Analyze preferences
            preference_analysis = await self._analyze_preference_patterns(profile.preferences)
            
            # Analyze behavior patterns
            behavior_analysis = await self._analyze_behavior_patterns(interactions)
            
            # Generate recommendations
            insights = {
                'user_id': user_id,
                'profile_summary': {
                    'primary_preferences': preference_analysis['primary_preferences'],
                    'travel_style': preference_analysis['travel_style'],
                    'budget_tendency': preference_analysis['budget_tendency']
                },
                'behavior_insights': {
                    'total_interactions': len(interactions),
                    'engagement_rate': behavior_analysis['engagement_rate'],
                    'preferred_categories': behavior_analysis['preferred_categories'],
                    'peak_activity_times': behavior_analysis['peak_activity_times']
                },
                'recommendation_accuracy': behavior_analysis['recommendation_accuracy'],
                'generated_at': datetime.utcnow()
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating user insights: {str(e)}")
            return None
    
    async def delete_user_profile(self, user_id: str) -> bool:
        """
        Delete user profile and all associated data.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False if user not found
        """
        try:
            logger.info(f"Deleting profile for user {user_id}")
            
            # Delete profile
            if user_id in self.user_profiles:
                del self.user_profiles[user_id]
            
            # Delete interactions
            if user_id in self.interactions:
                del self.interactions[user_id]
            
            logger.info(f"Successfully deleted profile for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user profile: {str(e)}")
            return False
    
    # Private helper methods
    
    async def _analyze_preferences(self, preferences: UserPreferences) -> UserPreferences:
        """
        Analyze and enhance user preferences using ML models.
        
        Args:
            preferences: Raw user preferences
            
        Returns:
            Enhanced preferences with ML insights
        """
        try:
            # In production, use ML model to analyze preferences
            # For now, return enhanced preferences with additional insights
            
            enhanced_preferences = UserPreferences(
                preferences=preferences.preferences or [TravelPreference.CULTURAL],
                budget_range=preferences.budget_range or {'min': 50, 'max': 200},
                travel_style=preferences.travel_style or 'mid-range',
                group_size=preferences.group_size or 2,
                accessibility_needs=preferences.accessibility_needs or [],
                dietary_restrictions=preferences.dietary_restrictions or [],
                language_preferences=preferences.language_preferences or ['English']
            )
            
            return enhanced_preferences
            
        except Exception as e:
            logger.error(f"Error analyzing preferences: {str(e)}")
            return preferences
    
    async def _update_preferences_from_interaction(self, interaction: UserInteraction):
        """
        Update user preferences based on interaction patterns.
        
        Args:
            interaction: User interaction data
        """
        try:
            # Get user profile
            profile = self.user_profiles.get(interaction.user_id)
            if not profile:
                return
            
            # In production, implement preference learning algorithm
            # For now, log the interaction for future analysis
            
            logger.info(f"Learning from interaction: {interaction.interaction_type} for activity {interaction.activity_id}")
            
        except Exception as e:
            logger.error(f"Error updating preferences from interaction: {str(e)}")
    
    async def _analyze_preference_patterns(self, preferences: UserPreferences) -> Dict[str, Any]:
        """Analyze preference patterns."""
        preference_list = preferences.preferences or []
        
        return {
            'primary_preferences': preference_list[:3] if preference_list else [],
            'travel_style': preferences.travel_style or 'mid-range',
            'budget_tendency': preferences.budget_range or {'min': 50, 'max': 200},
            'preference_diversity': len(preference_list)
        }
    
    async def _analyze_behavior_patterns(self, interactions: List[UserInteraction]) -> Dict[str, Any]:
        """Analyze user behavior patterns from interactions."""
        if not interactions:
            return {
                'engagement_rate': 0.0,
                'preferred_categories': [],
                'peak_activity_times': [],
                'recommendation_accuracy': 0.0
            }
        
        # Calculate engagement rate
        positive_interactions = sum(1 for i in interactions if i.interaction_type in ['like', 'save', 'book'])
        engagement_rate = positive_interactions / len(interactions) if interactions else 0.0
        
        # Analyze interaction types
        interaction_counts = {}
        for interaction in interactions:
            interaction_counts[interaction.interaction_type] = interaction_counts.get(interaction.interaction_type, 0) + 1
        
        # Calculate recommendation accuracy (mock)
        accuracy = min(engagement_rate * 1.2, 1.0)
        
        return {
            'engagement_rate': engagement_rate,
            'preferred_categories': list(interaction_counts.keys()),
            'peak_activity_times': ['morning', 'evening'],  # Mock data
            'recommendation_accuracy': accuracy,
            'interaction_breakdown': interaction_counts
        }
