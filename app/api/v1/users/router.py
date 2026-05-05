"""HTTP router for user profiles, preferences, and interactions.

Responsibilities:
    Profile CRUD, preference updates, interaction logging, history, and aggregated insights.

Dependencies:
    `UserServiceDep`, schemas in `app.modules.users.schemas`.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.deps import UserServiceDep
from app.modules.users.schemas import (
    UserInteraction,
    UserPreferences,
    UserProfile,
    UserProfileUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/profile", response_model=UserProfile)
async def create_user_profile(
    profile: UserProfile,
    service: UserServiceDep,
):
    """Creates a user profile persisted by the service.

    Args:
        profile: Profile payload.
        service: `UserService`.

    Returns:
        Created profile.

    Raises:
        HTTPException: 400 on validation; 500 on internal error.
    """
    try:
        logger.info("Creating profile for user %s", profile.user_id)
        created_profile = await service.create_user_profile(profile)
        logger.info("Successfully created profile for user %s", profile.user_id)
        return created_profile
    except ValueError as e:
        logger.error("Validation error creating profile: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error creating user profile: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create user profile")


@router.get("/profile/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str, service: UserServiceDep):
    """Fetches a profile by identifier.

    Args:
        user_id: User id.
        service: `UserService`.

    Returns:
        Profile when found.

    Raises:
        HTTPException: 404 if missing; 500 on internal error.
    """
    try:
        logger.info("Fetching profile for user %s", user_id)
        profile = await service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching user profile: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")


@router.put("/profile/{user_id}", response_model=UserProfile)
async def update_user_profile(
    user_id: str,
    profile_update: UserProfileUpdate,
    service: UserServiceDep,
):
    """Updates fields on an existing profile.

    Args:
        user_id: User id.
        profile_update: Fields to merge.
        service: `UserService`.

    Returns:
        Updated profile.

    Raises:
        HTTPException: 404 if not found; 400 on validation; 500 on internal error.
    """
    try:
        logger.info("Updating profile for user %s", user_id)
        updated_profile = await service.update_user_profile(user_id, profile_update)
        if not updated_profile:
            raise HTTPException(status_code=404, detail="User profile not found")
        logger.info("Successfully updated profile for user %s", user_id)
        return updated_profile
    except HTTPException:
        raise
    except ValueError as e:
        logger.error("Validation error updating profile: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error updating user profile: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update user profile")


@router.post("/preferences/{user_id}")
async def update_user_preferences(
    user_id: str,
    preferences: UserPreferences,
    service: UserServiceDep,
):
    """Persists travel preferences linked to the profile.

    Args:
        user_id: User id.
        preferences: Preference structure.
        service: `UserService`.

    Returns:
        Success message and `user_id`.

    Raises:
        HTTPException: 404 if no profile; 500 on internal error.
    """
    try:
        logger.info("Updating preferences for user %s", user_id)
        success = await service.update_user_preferences(user_id, preferences)
        if not success:
            raise HTTPException(status_code=404, detail="User profile not found")
        return {"message": "Preferences updated successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating user preferences: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update user preferences")


@router.post("/interaction")
async def record_user_interaction(interaction: UserInteraction, service: UserServiceDep):
    """Records an interaction (click, view, etc.) for learning or analytics.

    Args:
        interaction: Typed event.
        service: `UserService`.

    Returns:
        Confirmation with a related identifier.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        logger.info("Recording interaction for user %s", interaction.user_id)
        await service.record_interaction(interaction)
        return {"message": "Interaction recorded successfully", "interaction_id": interaction.user_id}
    except Exception as e:
        logger.error("Error recording interaction: %s", e)
        raise HTTPException(status_code=500, detail="Failed to record interaction")


@router.get("/history/{user_id}")
async def get_user_interaction_history(
    user_id: str,
    service: UserServiceDep,
    limit: int = 50,
):
    """Lists recent interactions for the user.

    Args:
        user_id: User id.
        service: `UserService`.
        limit: Max records (default 50).

    Returns:
        Dict with `interactions` and `total_count`.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        logger.info("Fetching interaction history for user %s", user_id)
        history = await service.get_interaction_history(user_id, limit)
        return {"user_id": user_id, "interactions": history, "total_count": len(history)}
    except Exception as e:
        logger.error("Error fetching interaction history: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch interaction history")


@router.get("/insights/{user_id}")
async def get_user_insights(user_id: str, service: UserServiceDep):
    """Builds a summary of behavior or inferred preferences.

    Args:
        user_id: User id.
        service: `UserService`.

    Returns:
        Insights payload from the service.

    Raises:
        HTTPException: 404 if no profile or data; 500 on internal error.
    """
    try:
        logger.info("Generating insights for user %s", user_id)
        insights = await service.generate_user_insights(user_id)
        if not insights:
            raise HTTPException(status_code=404, detail="User profile not found")
        return insights
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating user insights: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate user insights")


@router.delete("/profile/{user_id}")
async def delete_user_profile(user_id: str, service: UserServiceDep):
    """Deletes the profile and related data per service implementation.

    Args:
        user_id: User id.
        service: `UserService`.

    Returns:
        Success message and `user_id`.

    Raises:
        HTTPException: 404 if it did not exist; 500 on internal error.
    """
    try:
        logger.info("Deleting profile for user %s", user_id)
        success = await service.delete_user_profile(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User profile not found")
        return {"message": "User profile deleted successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting user profile: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete user profile")
