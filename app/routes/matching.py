"""
Traveler matching API routes.

Endpoints for finding compatible travel partners based on
preferences, travel styles, and compatibility scores.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import logging

from app.models.schemas import (
    TravelerMatchRequest,
    TravelerMatch,
    MatchingResponse,
    APIResponse
)
from app.services.matching_service import MatchingService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_matching_service(request: Request) -> MatchingService:
    """Dependency injection for matching service."""
    model_manager = getattr(request.app.state, 'model_manager', None)
    if not model_manager or not model_manager.is_ready():
        raise HTTPException(status_code=503, detail="ML models not loaded")
    
    return MatchingService(model_manager)


@router.post("/find", response_model=MatchingResponse)
async def find_travel_partners(
    request_data: TravelerMatchRequest,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Find compatible travel partners.
    
    - **user_id**: Unique identifier for the user
    - **location**: Travel destination
    - **travel_dates**: Travel date range
    - **preferences**: Optional travel preferences
    - **max_matches**: Maximum number of matches to return
    
    Returns a list of compatible travelers with compatibility scores.
    """
    try:
        logger.info(f"Finding travel partners for user {request_data.user_id}")
        
        matches = await service.find_travel_partners(request_data)
        
        logger.info(f"Found {len(matches.matches)} matches for user {request_data.user_id}")
        return matches
        
    except Exception as e:
        logger.error(f"Error finding travel partners: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to find travel partners")


@router.get("/compatibility/{user_id}/{target_user_id}")
async def get_compatibility_score(
    user_id: str,
    target_user_id: str,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Get compatibility score between two users.
    
    - **user_id**: First user identifier
    - **target_user_id**: Second user identifier
    
    Returns detailed compatibility analysis between two users.
    """
    try:
        logger.info(f"Calculating compatibility between {user_id} and {target_user_id}")
        
        compatibility = await service.calculate_compatibility(user_id, target_user_id)
        
        if not compatibility:
            raise HTTPException(status_code=404, detail="One or both users not found")
        
        return compatibility
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating compatibility: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate compatibility")


@router.post("/connect/{user_id}/{target_user_id}")
async def initiate_connection(
    user_id: str,
    target_user_id: str,
    message: Optional[str] = None,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Initiate connection with a matched traveler.
    
    - **user_id**: User identifier initiating the connection
    - **target_user_id**: Target user identifier
    - **message**: Optional connection message
    
    Creates a connection request between two users.
    """
    try:
        logger.info(f"Initiating connection from {user_id} to {target_user_id}")
        
        connection = await service.initiate_connection(user_id, target_user_id, message)
        
        return {
            "message": "Connection request sent successfully",
            "connection_id": connection.get("connection_id"),
            "user_id": user_id,
            "target_user_id": target_user_id
        }
        
    except Exception as e:
        logger.error(f"Error initiating connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate connection")


@router.get("/connections/{user_id}")
async def get_user_connections(
    user_id: str,
    status: Optional[str] = None,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Get user's connections and connection requests.
    
    - **user_id**: User identifier
    - **status**: Optional status filter (pending, accepted, declined)
    
    Returns all connections for the specified user.
    """
    try:
        logger.info(f"Fetching connections for user {user_id}")
        
        connections = await service.get_user_connections(user_id, status)
        
        return {
            "user_id": user_id,
            "connections": connections,
            "total_count": len(connections)
        }
        
    except Exception as e:
        logger.error(f"Error fetching connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch connections")


@router.put("/connections/{connection_id}/respond")
async def respond_to_connection(
    connection_id: str,
    response: str,  # accept, decline
    message: Optional[str] = None,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Respond to a connection request.
    
    - **connection_id**: Connection identifier
    - **response**: Response type (accept, decline)
    - **message**: Optional response message
    
    Updates the connection request status.
    """
    try:
        if response not in ["accept", "decline"]:
            raise HTTPException(status_code=400, detail="Response must be 'accept' or 'decline'")
        
        logger.info(f"Responding to connection {connection_id} with {response}")
        
        updated_connection = await service.respond_to_connection(connection_id, response, message)
        
        if not updated_connection:
            raise HTTPException(status_code=404, detail="Connection request not found")
        
        return {
            "message": f"Connection {response}ed successfully",
            "connection_id": connection_id,
            "status": response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error responding to connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to respond to connection")


@router.get("/recommendations/{user_id}")
async def get_travel_buddy_recommendations(
    user_id: str,
    location: Optional[str] = None,
    limit: int = 10,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Get travel buddy recommendations based on user preferences.
    
    - **user_id**: User identifier
    - **location**: Optional location filter
    - **limit**: Maximum number of recommendations
    
    Returns recommended travel buddies for the user.
    """
    try:
        logger.info(f"Getting travel buddy recommendations for user {user_id}")
        
        recommendations = await service.get_travel_buddy_recommendations(user_id, location, limit)
        
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "total_count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error getting travel buddy recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get travel buddy recommendations")


@router.post("/feedback/{user_id}/{target_user_id}")
async def submit_match_feedback(
    user_id: str,
    target_user_id: str,
    rating: int,
    feedback_text: Optional[str] = None,
    service: MatchingService = Depends(get_matching_service)
):
    """
    Submit feedback for a travel match.
    
    - **user_id**: User identifier
    - **target_user_id**: Matched user identifier
    - **rating**: Rating from 1-5
    - **feedback_text**: Optional detailed feedback
    
    Records feedback to improve matching algorithms.
    """
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        
        logger.info(f"Recording match feedback from {user_id} for {target_user_id}")
        
        await service.record_match_feedback(user_id, target_user_id, rating, feedback_text)
        
        return {
            "message": "Match feedback recorded successfully",
            "user_id": user_id,
            "target_user_id": target_user_id,
            "rating": rating
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording match feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record match feedback")
