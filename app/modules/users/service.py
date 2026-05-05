"""User profile and interaction service (in-memory demo store).

Purpose:
    Create and update profiles, normalize preferences, record interactions,
    and surface lightweight analytics for personalization layers.

Responsibilities:
    CRUD-style profile operations, capped interaction history, and insight payloads.

Dependencies:
    ``settings``, common enums, ``users.schemas``, ``model_manager`` (constructor).
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta, timezone

from app.modules.common.schemas.enums import TravelPreference
from app.modules.users.schemas import (
    UserProfile,
    UserProfileUpdate,
    UserPreferences,
    UserInteraction,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserService:
    """In-memory user store with preference normalization hooks.

    Attributes:
        model_manager: Reserved ML entry point for future enrichment.
        user_profiles: Map of ``user_id`` to ``UserProfile``.
        interactions: Map of ``user_id`` to chronological ``UserInteraction`` list.
    """

    def __init__(self, model_manager):
        """Creates the service with an attached model manager.

        Args:
            model_manager: Shared ``ModelManager`` instance from the app container.
        """
        self.model_manager = model_manager
        self.user_profiles = {}  # In-memory storage (replace with database in production)
        self.interactions = {}  # Store user interactions
    
    def create_user_profile(self, profile: UserProfile) -> UserProfile:
        """Persists a new profile after validation and preference analysis.

        Args:
            profile: Incoming profile; email must contain ``@``.

        Returns:
            Stored ``UserProfile`` with analyzed preferences and timestamps.

        Raises:
            ValueError: If the user already exists or email format is invalid.
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
            analyzed_preferences = self._analyze_preferences(profile.preferences)
            
            # Create enhanced profile
            enhanced_profile = UserProfile(
                user_id=profile.user_id,
                name=profile.name,
                email=profile.email,
                age=profile.age,
                location=profile.location,
                preferences=analyzed_preferences,
                travel_history=profile.travel_history,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
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
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Fetches a profile by id.

        Args:
            user_id: Primary key for the in-memory store.

        Returns:
            ``UserProfile`` if present, else ``None`` (also on unexpected errors).
        """
        try:
            return self.user_profiles.get(user_id)
        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}")
            return None
    
    def update_user_profile(self, user_id: str, profile_update: UserProfileUpdate) -> Optional[UserProfile]:
        """Merges partial updates; re-runs preference analysis when preferences change.

        Args:
            user_id: Target user.
            profile_update: Fields to merge (preferences, location, travel history).

        Returns:
            Updated ``UserProfile``, or ``None`` if the user does not exist or on error.
        """
        try:
            logger.info("Updating user profile")
            
            # Get existing profile
            existing_profile = self.user_profiles.get(user_id)
            if not existing_profile:
                return None
            
            # Update fields
            if profile_update.preferences:
                analyzed_preferences = self._analyze_preferences(profile_update.preferences)
                existing_profile.preferences = analyzed_preferences
            
            if profile_update.location:
                existing_profile.location = profile_update.location
            
            if profile_update.travel_history:
                existing_profile.travel_history = profile_update.travel_history
            
            existing_profile.updated_at = datetime.now(timezone.utc)
            
            # Store updated profile
            self.user_profiles[user_id] = existing_profile
            
            logger.info("Successfully updated user profile")
            return existing_profile
            
        except Exception as e:
            logger.error(f"Error updating user profile: {str(e)}")
            return None
    
    def update_user_preferences(self, user_id: str, preferences: UserPreferences) -> bool:
        """Replaces the user's ``UserPreferences`` block after analysis.

        Args:
            user_id: Target user.
            preferences: New preference payload.

        Returns:
            ``True`` if updated, ``False`` if the user is missing or on error.
        """
        try:
            logger.info("Updating user preferences")
            
            # Get existing profile
            existing_profile = self.user_profiles.get(user_id)
            if not existing_profile:
                return False
            
            # Analyze and update preferences
            analyzed_preferences = self._analyze_preferences(preferences)
            existing_profile.preferences = analyzed_preferences
            existing_profile.updated_at = datetime.now(timezone.utc)
            
            # Store updated profile
            self.user_profiles[user_id] = existing_profile
            
            logger.info("Successfully updated user preferences")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {str(e)}")
            return False
    
    def record_interaction(self, interaction: UserInteraction):
        """Appends an interaction and triggers a preference-learning hook.

        Args:
            interaction: Typed interaction record for the user.

        Raises:
            Exception: Propagates unexpected storage errors after logging.
        """
        try:
            logger.info(f"Recording interaction for user {interaction.user_id}")
            
            # Store interaction
            if interaction.user_id not in self.interactions:
                self.interactions[interaction.user_id] = []
            
            self.interactions[interaction.user_id].append(interaction)
            
            # Update user preferences based on interaction
            self._update_preferences_from_interaction(interaction)
            
            # Limit interaction history
            max_interactions = 1000
            if len(self.interactions[interaction.user_id]) > max_interactions:
                self.interactions[interaction.user_id] = self.interactions[interaction.user_id][-max_interactions:]
            
        except Exception as e:
            logger.error(f"Error recording interaction: {str(e)}")
            raise
    
    def get_interaction_history(self, user_id: str, limit: int) -> List[UserInteraction]:
        """Returns the most recent interactions, optionally capped.

        Args:
            user_id: Target user.
            limit: Max items; ``<= 0`` returns the full stored list.

        Returns:
            Slice of interactions newest-last, or empty list on error.
        """
        try:
            user_interactions = self.interactions.get(user_id, [])
            return user_interactions[-limit:] if limit > 0 else user_interactions
        except Exception as e:
            logger.error(f"Error fetching interaction history: {str(e)}")
            return []
    
    def generate_user_insights(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Builds a dashboard-oriented summary from profile and interaction history.

        Args:
            user_id: Target user.

        Returns:
            Structured insights dict, or ``None`` if the profile is missing or on error.
        """
        try:
            logger.info("Generating user insights")
            
            # Get user profile
            profile = self.user_profiles.get(user_id)
            if not profile:
                return None
            
            # Get interaction history
            interactions = self.interactions.get(user_id, [])
            
            # Analyze preferences
            preference_analysis = self._analyze_preference_patterns(profile.preferences)
            
            # Analyze behavior patterns
            behavior_analysis = self._analyze_behavior_patterns(interactions)
            
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
                'generated_at': datetime.now(timezone.utc)
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating user insights: {str(e)}")
            return None
    
    def delete_user_profile(self, user_id: str) -> bool:
        """Removes profile and interaction rows for the user.

        Args:
            user_id: Target user.

        Returns:
            ``True`` on success, ``False`` if deletion raises after logging.
        """
        try:
            logger.info("Deleting user profile")
            
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
    
    def _analyze_preferences(self, preferences: UserPreferences) -> UserPreferences:
        """Fills sensible defaults and placeholder enrichment for preferences.

        Args:
            preferences: Source preferences object.

        Returns:
            Normalized ``UserPreferences``; falls back to input on error.
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
    
    def _update_preferences_from_interaction(self, interaction: UserInteraction):
        """Hook for future online learning; currently logs only.

        Args:
            interaction: Latest user interaction.
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
    
    def _analyze_preference_patterns(self, preferences: UserPreferences) -> Dict[str, Any]:
        """Derives a compact preference summary for insight payloads."""
        preference_list = preferences.preferences or []
        
        return {
            'primary_preferences': preference_list[:3] if preference_list else [],
            'travel_style': preferences.travel_style or 'mid-range',
            'budget_tendency': preferences.budget_range or {'min': 50, 'max': 200},
            'preference_diversity': len(preference_list)
        }
    
    def _analyze_behavior_patterns(self, interactions: List[UserInteraction]) -> Dict[str, Any]:
        """Computes engagement and coarse behavioral stats from stored interactions."""
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
