"""
Users API routes.

Endpoints for user profile management, preference tracking,
and user behavior analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional
import logging

from app.models.schemas import (
    UserProfile,
    UserProfileUpdate,
    UserPreferences,
    UserInteraction,
    APIResponse
)
from app.services.user_service import UserService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_user_service(request: Request) -> UserService:
    """Dependency injection for user service."""
    model_manager = getattr(request.app.state, 'model_manager', None)
    if not model_manager or not model_manager.is_ready():
        raise HTTPException(status_code=503, detail="ML models not loaded")
    
    return UserService(model_manager)


@router.post("/profile", response_model=UserProfile)
async def create_user_profile(
    profile: UserProfile,
    service: UserService = Depends(get_user_service)
):
    """
    Create a new user profile.
    
    - **user_id**: Unique identifier for the user
    - **name**: User's name
    - **email**: User's email address
    - **preferences**: Travel preferences
    - **location**: Current location
    - **travel_history**: Past travel experiences
    
    Creates a new user profile with preference analysis.
    """
    try:
        logger.info(f"Creating profile for user {profile.user_id}")
        
        created_profile = await service.create_user_profile(profile)
        
        logger.info(f"Successfully created profile for user {profile.user_id}")
        return created_profile
        
    except ValueError as e:
        logger.error(f"Validation error creating profile: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create user profile")


@router.get("/profile/{user_id}", response_model=UserProfile)
async def get_user_profile(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    Get user profile by ID.
    
    - **user_id**: Unique identifier for the user
    
    Returns the complete user profile including preferences and travel history.
    """
    try:
        logger.info(f"Fetching profile for user {user_id}")
        
        profile = await service.get_user_profile(user_id)
        
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")


@router.put("/profile/{user_id}", response_model=UserProfile)
async def update_user_profile(
    user_id: str,
    profile_update: UserProfileUpdate,
    service: UserService = Depends(get_user_service)
):
    """
    Update user profile.
    
    - **user_id**: Unique identifier for the user
    - **preferences**: Updated travel preferences
    - **location**: Updated location
    - **travel_history**: Updated travel history
    
    Updates specific fields in the user profile.
    """
    try:
        logger.info(f"Updating profile for user {user_id}")
        
        updated_profile = await service.update_user_profile(user_id, profile_update)
        
        if not updated_profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        logger.info(f"Successfully updated profile for user {user_id}")
        return updated_profile
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating profile: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user profile")


@router.post("/preferences/{user_id}")
async def update_user_preferences(
    user_id: str,
    preferences: UserPreferences,
    service: UserService = Depends(get_user_service)
):
    """
    Update user preferences specifically.
    
    - **user_id**: Unique identifier for the user
    - **preferences**: New travel preferences
    
    Updates only the preferences section of the user profile.
    """
    try:
        logger.info(f"Updating preferences for user {user_id}")
        
        success = await service.update_user_preferences(user_id, preferences)
        
        if not success:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return {"message": "Preferences updated successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user preferences")


@router.post("/interaction")
async def record_user_interaction(
    interaction: UserInteraction,
    service: UserService = Depends(get_user_service)
):
    """
    Record user interaction with recommendations.
    
    - **user_id**: User identifier
    - **activity_id**: Activity identifier
    - **interaction_type**: Type of interaction (view, like, save, book, dismiss)
    - **context**: Additional context information
    
    Records user interactions for preference learning and recommendation improvement.
    """
    try:
        logger.info(f"Recording interaction for user {interaction.user_id}")
        
        await service.record_interaction(interaction)
        
        return {"message": "Interaction recorded successfully", "interaction_id": interaction.user_id}
        
    except Exception as e:
        logger.error(f"Error recording interaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record interaction")


@router.get("/history/{user_id}")
async def get_user_interaction_history(
    user_id: str,
    limit: int = 50,
    service: UserService = Depends(get_user_service)
):
    """
    Get user interaction history.
    
    - **user_id**: User identifier
    - **limit**: Maximum number of interactions to return
    
    Returns the user's interaction history with recommendations.
    """
    try:
        logger.info(f"Fetching interaction history for user {user_id}")
        
        history = await service.get_interaction_history(user_id, limit)
        
        return {
            "user_id": user_id,
            "interactions": history,
            "total_count": len(history)
        }
        
    except Exception as e:
        logger.error(f"Error fetching interaction history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch interaction history")


@router.get("/insights/{user_id}")
async def get_user_insights(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    Get user behavior insights and analytics.
    
    - **user_id**: User identifier
    
    Returns insights about user preferences, behavior patterns, and recommendations.
    """
    try:
        logger.info(f"Generating insights for user {user_id}")
        
        insights = await service.generate_user_insights(user_id)
        
        if not insights:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return insights
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating user insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate user insights")


@router.delete("/profile/{user_id}")
async def delete_user_profile(
    user_id: str,
    service: UserService = Depends(get_user_service)
):
    """
    Delete user profile and all associated data.
    
    - **user_id**: User identifier
    
    Permanently deletes the user profile and all related data.
    """
    try:
        logger.info(f"Deleting profile for user {user_id}")
        
        success = await service.delete_user_profile(user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="User profile not found")
        
        return {"message": "User profile deleted successfully", "user_id": user_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete user profile")
