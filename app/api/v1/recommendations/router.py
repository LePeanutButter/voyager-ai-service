"""
Recommendations API routes.
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


@router.post("/destinations/personalized", response_model=DestinationRecommendationResponse)
async def get_personalized_destinations(
    body: DestinationRecommendationRequest,
    service: RecommendationServiceDep,
):
    try:
        return await service.get_personalized_destinations(body)
    except Exception as e:
        logger.error("Error generating destination recommendations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate destination recommendations")


@router.post("/activities/contextual", response_model=ContextualActivityResponse)
async def get_contextual_activities(
    body: ContextualActivityRequest,
    service: RecommendationServiceDep,
):
    try:
        return await service.get_contextual_activities(body)
    except Exception as e:
        logger.error("Error generating contextual activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate contextual activities")


@router.post("/personalized", response_model=RecommendationResponse)
async def get_personalized_recommendations(
    request_data: RecommendationRequest,
    service: RecommendationServiceDep,
):
    try:
        logger.info("Generating recommendations for user %s", request_data.user_id)
        recommendations = await service.generate_recommendations(request_data)
        logger.info("Generated %s recommendations", len(recommendations.recommendations))
        return recommendations
    except Exception as e:
        logger.error("Error generating recommendations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@router.get("/popular/{location}")
async def get_popular_activities(
    service: RecommendationServiceDep,
    location: str,
    limit: int = 10,
):
    try:
        logger.info("Fetching popular activities for %s", location)
        activities = await service.get_popular_activities(location, limit)
        return {"location": location, "activities": activities, "total_results": len(activities)}
    except Exception as e:
        logger.error("Error fetching popular activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch popular activities")


@router.get("/trending")
async def get_trending_activities(
    service: RecommendationServiceDep,
    category: Optional[str] = None,
    limit: int = 10,
):
    try:
        logger.info("Fetching trending activities for category: %s", category)
        activities = await service.get_trending_activities(category, limit)
        return {"category": category, "activities": activities, "total_results": len(activities)}
    except Exception as e:
        logger.error("Error fetching trending activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch trending activities")


@router.get("/similar/{activity_id}")
async def get_similar_activities(
    service: RecommendationServiceDep,
    activity_id: str,
    limit: int = 5,
):
    try:
        logger.info("Fetching activities similar to %s", activity_id)
        similar_activities = await service.get_similar_activities(activity_id, limit)
        return {
            "reference_activity_id": activity_id,
            "similar_activities": similar_activities,
            "total_results": len(similar_activities),
        }
    except Exception as e:
        logger.error("Error fetching similar activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch similar activities")


@router.post("/feedback")
async def submit_recommendation_feedback(
    service: RecommendationServiceDep,
    user_id: str,
    activity_id: str,
    rating: int,
    feedback_text: Optional[str] = None,
):
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        logger.info("Recording feedback from user %s for activity %s", user_id, activity_id)
        await service.record_feedback(user_id, activity_id, rating, feedback_text)
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


@router.get("/categories")
async def get_activity_categories(service: RecommendationServiceDep):
    try:
        categories = await service.get_activity_categories()
        return {"categories": categories, "total_count": len(categories)}
    except Exception as e:
        logger.error("Error fetching categories: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch categories")
