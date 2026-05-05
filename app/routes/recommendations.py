"""
Recommendations API routes.

Endpoints for generating personalized travel recommendations
based on user preferences, location, and context.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import logging

from app.models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    Activity,
    APIResponse,
    DestinationRecommendationRequest,
    DestinationRecommendationResponse,
    ContextualActivityRequest,
    ContextualActivityResponse,
)
from app.services.recommendation_service import RecommendationService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_recommendation_service(request: Request) -> RecommendationService:
    """Dependency injection for recommendation service."""
    model_manager = getattr(request.app.state, 'model_manager', None)
    if not model_manager or not model_manager.is_ready():
        raise HTTPException(status_code=503, detail="ML models not loaded")
    trends_service = getattr(request.app.state, "trends_service", None)

    return RecommendationService(model_manager, trends_service=trends_service)


@router.post("/destinations/personalized", response_model=DestinationRecommendationResponse)
async def get_personalized_destinations(
    body: DestinationRecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service),
):
    """
    PBI 24: destinos personalizados con puntuación de compatibilidad y sesgo a patrones exitosos.
    """
    try:
        return await service.get_personalized_destinations(body)
    except Exception as e:
        logger.error("Error generating destination recommendations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate destination recommendations")


@router.post("/activities/contextual", response_model=ContextualActivityResponse)
async def get_contextual_activities(
    body: ContextualActivityRequest,
    service: RecommendationService = Depends(get_recommendation_service),
):
    """
    PBI 25: actividades en tiempo real según ubicación, clima y preferencias (prioriza indoor si el clima es adverso).
    """
    try:
        return await service.get_contextual_activities(body)
    except Exception as e:
        logger.error("Error generating contextual activities: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate contextual activities")


@router.post("/personalized", response_model=RecommendationResponse)
async def get_personalized_recommendations(
    request_data: RecommendationRequest,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Generate personalized travel recommendations.
    
    - **user_id**: Unique identifier for the user
    - **location**: Current location or destination
    - **preferences**: Optional travel preferences
    - **max_results**: Maximum number of recommendations to return
    - **date_range**: Optional travel date range
    - **group_size**: Optional group size
    - **budget_limit**: Optional budget constraint
    
    Returns personalized activity recommendations with confidence scores.
    """
    try:
        logger.info(f"Generating recommendations for user {request_data.user_id}")
        
        recommendations = await service.generate_recommendations(request_data)
        
        logger.info(f"Generated {len(recommendations.recommendations)} recommendations")
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")


@router.get("/popular/{location}")
async def get_popular_activities(
    location: str,
    limit: int = 10,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Get popular activities for a specific location.
    
    - **location**: City or destination name
    - **limit**: Maximum number of activities to return
    
    Returns trending and highly-rated activities for the given location.
    """
    try:
        logger.info(f"Fetching popular activities for {location}")
        
        activities = await service.get_popular_activities(location, limit)
        
        return {
            "location": location,
            "activities": activities,
            "total_results": len(activities)
        }
        
    except Exception as e:
        logger.error(f"Error fetching popular activities: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch popular activities")


@router.get("/trending")
async def get_trending_activities(
    category: Optional[str] = None,
    limit: int = 10,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Get trending activities globally or by category.
    
    - **category**: Optional activity category filter
    - **limit**: Maximum number of activities to return
    
    Returns currently trending activities based on user engagement.
    """
    try:
        logger.info(f"Fetching trending activities for category: {category}")
        
        activities = await service.get_trending_activities(category, limit)
        
        return {
            "category": category,
            "activities": activities,
            "total_results": len(activities)
        }
        
    except Exception as e:
        logger.error(f"Error fetching trending activities: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch trending activities")


@router.get("/similar/{activity_id}")
async def get_similar_activities(
    activity_id: str,
    limit: int = 5,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Get activities similar to a specific activity.
    
    - **activity_id**: ID of the reference activity
    - **limit**: Maximum number of similar activities to return
    
    Returns activities with similar characteristics and user preferences.
    """
    try:
        logger.info(f"Fetching activities similar to {activity_id}")
        
        similar_activities = await service.get_similar_activities(activity_id, limit)
        
        return {
            "reference_activity_id": activity_id,
            "similar_activities": similar_activities,
            "total_results": len(similar_activities)
        }
        
    except Exception as e:
        logger.error(f"Error fetching similar activities: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch similar activities")


@router.post("/feedback")
async def submit_recommendation_feedback(
    user_id: str,
    activity_id: str,
    rating: int,
    feedback_text: Optional[str] = None,
    service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Submit feedback for recommendations to improve future suggestions.
    
    - **user_id**: User identifier
    - **activity_id**: Activity identifier
    - **rating**: Rating from 1-5
    - **feedback_text**: Optional detailed feedback
    
    Records user feedback for ML model improvement.
    """
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        logger.info(f"Recording feedback from user {user_id} for activity {activity_id}")
        
        await service.record_feedback(user_id, activity_id, rating, feedback_text)
        
        return {
            "message": "Feedback recorded successfully",
            "user_id": user_id,
            "activity_id": activity_id,
            "rating": rating
        }
        
    except Exception as e:
        logger.error(f"Error recording feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record feedback")


@router.get("/categories")
async def get_activity_categories(
    service: RecommendationService = Depends(get_recommendation_service)
):
    """
    Get available activity categories.
    
    Returns all supported activity categories for filtering and preferences.
    """
    try:
        categories = await service.get_activity_categories()
        
        return {
            "categories": categories,
            "total_count": len(categories)
        }
        
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")
