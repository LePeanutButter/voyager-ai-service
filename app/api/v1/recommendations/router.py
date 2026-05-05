"""HTTP router for destination and activity recommendations and feedback.

Responsibilities:
    Personalized and contextual recommendations, popular/trending/similar listings,
    categories, and rating capture.

Dependencies:
    `RecommendationServiceDep`, schemas in `app.modules.recommendations.schemas`.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.api.deps import RecommendationServiceDep
from app.modules.recommendations.schemas import (
    ContextualActivityRequest,
    ContextualActivityResponse,
    DestinationRecommendationRequest,
    DestinationRecommendationResponse,
    RecommendationRequest,
    RecommendationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/destinations/personalized",
    response_model=DestinationRecommendationResponse,
    responses={500: {"description": "Failed to generate destination recommendations"}},
)
async def get_personalized_destinations(
    body: DestinationRecommendationRequest,
    service: RecommendationServiceDep,
):
    """Recommends destinations from profile and request constraints.

    Args:
        body: Destination and user criteria.
        service: `RecommendationService`.

    Returns:
        Ranked destination list.

    Raises:
        HTTPException: 500 if the engine or LLM path fails.
    """
    try:
        return service.get_personalized_destinations(body)
    except Exception as e:
        logger.error("Error generating destination recommendations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate destination recommendations")


@router.post(
    "/activities/contextual",
    response_model=ContextualActivityResponse,
    responses={500: {"description": "Failed to generate contextual activities"}},
)
async def get_contextual_activities(
    body: ContextualActivityRequest,
    service: RecommendationServiceDep,
):
    """Suggests activities scoped by location, time window, and trip context.

    Args:
        body: Location, time window, and preferences.
        service: `RecommendationService`.

    Returns:
        Contextual activities payload.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        return service.get_contextual_activities(body)
    except Exception as e:
        logger.error("Error generating contextual activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate contextual activities")


@router.post(
    "/personalized",
    response_model=RecommendationResponse,
    responses={500: {"description": "Failed to generate recommendations"}},
)
async def get_personalized_recommendations(
    request_data: RecommendationRequest,
    service: RecommendationServiceDep,
):
    """Generates general recommendations (activities or offers) for the user.

    Args:
        request_data: Request id and filters.
        service: `RecommendationService`.

    Returns:
        Recommendations collection with metadata.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        logger.info("Generating recommendations for user %s", request_data.user_id)
        recommendations = service.generate_recommendations(request_data)
        logger.info("Generated %s recommendations", len(recommendations.recommendations))
        return recommendations
    except Exception as e:
        logger.error("Error generating recommendations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@router.get(
    "/popular/{location}",
    responses={500: {"description": "Failed to fetch popular activities"}},
)
async def get_popular_activities(
    service: RecommendationServiceDep,
    location: str,
    limit: int = 10,
):
    """Most in-demand activities for a location.

    Args:
        service: `RecommendationService`.
        location: City or region.
        limit: Max results.

    Returns:
        Dict with `activities` and `total_results`.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        logger.info("Fetching popular activities")
        activities = service.get_popular_activities(location, limit)
        return {"location": location, "activities": activities, "total_results": len(activities)}
    except Exception as e:
        logger.error("Error fetching popular activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch popular activities")


@router.get(
    "/trending",
    responses={500: {"description": "Failed to fetch trending activities"}},
)
async def get_trending_activities(
    service: RecommendationServiceDep,
    category: Optional[str] = None,
    limit: int = 10,
):
    """Activities with strongest momentum, optionally filtered by category.

    Args:
        service: `RecommendationService`.
        category: Optional filter.
        limit: Max results.

    Returns:
        Dict with `category`, `activities`, and `total_results`.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        logger.info("Fetching trending activities for category: %s", category)
        activities = service.get_trending_activities(category, limit)
        return {"category": category, "activities": activities, "total_results": len(activities)}
    except Exception as e:
        logger.error("Error fetching trending activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch trending activities")


@router.get(
    "/similar/{activity_id}",
    responses={500: {"description": "Failed to fetch similar activities"}},
)
async def get_similar_activities(
    service: RecommendationServiceDep,
    activity_id: str,
    limit: int = 5,
):
    """Activities semantically or rule-close to the reference item.

    Args:
        service: `RecommendationService`.
        activity_id: Reference activity.
        limit: Max neighbors.

    Returns:
        Dict with `similar_activities` and counts.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        logger.info("Fetching activities similar to %s", activity_id)
        similar_activities = service.get_similar_activities(activity_id, limit)
        return {
            "reference_activity_id": activity_id,
            "similar_activities": similar_activities,
            "total_results": len(similar_activities),
        }
    except Exception as e:
        logger.error("Error fetching similar activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch similar activities")


@router.post(
    "/feedback",
    responses={
        400: {"description": "Rating must be between 1 and 5"},
        500: {"description": "Failed to record feedback"},
    },
)
async def submit_recommendation_feedback(
    service: RecommendationServiceDep,
    user_id: str,
    activity_id: str,
    rating: int,
    feedback_text: Optional[str] = None,
):
    """Records the user's rating for a recommendation.

    Args:
        service: `RecommendationService`.
        user_id: Rater id.
        activity_id: Rated activity.
        rating: Integer 1–5.
        feedback_text: Optional comment.

    Returns:
        Confirmation with ids and rating.

    Raises:
        HTTPException: 400 if rating is out of range; 500 on internal error.
    """
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        logger.info("Recording feedback from user %s for activity %s", user_id, activity_id)
        service.record_feedback(user_id, activity_id, rating, feedback_text)
        return {
            "message": "Feedback recorded successfully",
            "user_id": user_id,
            "activity_id": activity_id,
            "rating": rating,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error recording feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to record feedback")


@router.get(
    "/categories",
    responses={500: {"description": "Failed to fetch categories"}},
)
async def get_activity_categories(service: RecommendationServiceDep):
    """Lists categories available to filter or tag activities.

    Args:
        service: `RecommendationService`.

    Returns:
        Dict with `categories` and `total_count`.

    Raises:
        HTTPException: 500 on internal error.
    """
    try:
        categories = service.get_activity_categories()
        return {"categories": categories, "total_count": len(categories)}
    except Exception as e:
        logger.error("Error fetching categories: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch categories")
