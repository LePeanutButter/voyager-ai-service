"""
Traveler matching API routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.api.deps import MatchingServiceDep
from app.modules.matching.schemas import (
    ConnectionOutcomeRequest,
    ConnectionOutcomeResponse,
    MatchingResponse,
    TravelerMatchRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/find", response_model=MatchingResponse)
async def find_travel_partners(
    request_data: TravelerMatchRequest,
    service: MatchingServiceDep,
):
    try:
        logger.info("Finding travel partners for user %s", request_data.user_id)
        matches = await service.find_travel_partners(request_data)
        logger.info("Found %s matches for user %s", len(matches.matches), request_data.user_id)
        return matches
    except Exception as e:
        logger.error("Error finding travel partners: %s", e)
        raise HTTPException(status_code=500, detail="Failed to find travel partners")


@router.get("/compatibility/{user_id}/{target_user_id}")
async def get_compatibility_score(
    user_id: str,
    target_user_id: str,
    service: MatchingServiceDep,
):
    try:
        logger.info("Calculating compatibility between %s and %s", user_id, target_user_id)
        compatibility = await service.calculate_compatibility(user_id, target_user_id)
        if not compatibility:
            raise HTTPException(status_code=404, detail="One or both users not found")
        return compatibility
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error calculating compatibility: %s", e)
        raise HTTPException(status_code=500, detail="Failed to calculate compatibility")


@router.post("/connect/{user_id}/{target_user_id}")
async def initiate_connection(
    service: MatchingServiceDep,
    user_id: str,
    target_user_id: str,
    message: Optional[str] = None,
):
    try:
        logger.info("Initiating connection from %s to %s", user_id, target_user_id)
        connection = await service.initiate_connection(user_id, target_user_id, message)
        return {
            "message": "Connection request sent successfully",
            "connection_id": connection.get("connection_id"),
            "user_id": user_id,
            "target_user_id": target_user_id,
        }
    except Exception as e:
        logger.error("Error initiating connection: %s", e)
        raise HTTPException(status_code=500, detail="Failed to initiate connection")


@router.get("/connections/{user_id}")
async def get_user_connections(
    user_id: str,
    service: MatchingServiceDep,
    status: Optional[str] = None,
):
    try:
        logger.info("Fetching connections for user %s", user_id)
        connections = await service.get_user_connections(user_id, status)
        return {"user_id": user_id, "connections": connections, "total_count": len(connections)}
    except Exception as e:
        logger.error("Error fetching connections: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch connections")


@router.put("/connections/{connection_id}/respond")
async def respond_to_connection(
    connection_id: str,
    response: str,
    service: MatchingServiceDep,
    message: Optional[str] = None,
):
    try:
        if response not in ["accept", "decline"]:
            raise HTTPException(status_code=400, detail="Response must be 'accept' or 'decline'")
        logger.info("Responding to connection %s with %s", connection_id, response)
        updated_connection = await service.respond_to_connection(connection_id, response, message)
        if not updated_connection:
            raise HTTPException(status_code=404, detail="Connection request not found")
        return {
            "message": f"Connection {response}ed successfully",
            "connection_id": connection_id,
            "status": response,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error responding to connection: %s", e)
        raise HTTPException(status_code=500, detail="Failed to respond to connection")


@router.get("/recommendations/{user_id}")
async def get_travel_buddy_recommendations(
    user_id: str,
    service: MatchingServiceDep,
    location: Optional[str] = None,
    limit: int = 10,
):
    try:
        logger.info("Getting travel buddy recommendations for user %s", user_id)
        recommendations = await service.get_travel_buddy_recommendations(user_id, location, limit)
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "total_count": len(recommendations),
        }
    except Exception as e:
        logger.error("Error getting travel buddy recommendations: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get travel buddy recommendations")


@router.post("/learning/connection-outcome", response_model=ConnectionOutcomeResponse)
async def submit_connection_outcome(
    body: ConnectionOutcomeRequest,
    service: MatchingServiceDep,
):
    try:
        weights = await service.process_connection_outcome(
            body.user_id,
            body.target_user_id,
            body.outcome,
            body.dimension_snapshot,
            body.notes,
        )
        return ConnectionOutcomeResponse(status="ok", updated_weights=weights)
    except Exception as e:
        logger.error("Error recording connection outcome: %s", e)
        raise HTTPException(status_code=500, detail="Failed to record connection outcome")


@router.post("/feedback/{user_id}/{target_user_id}")
async def submit_match_feedback(
    user_id: str,
    target_user_id: str,
    service: MatchingServiceDep,
    rating: int,
    feedback_text: Optional[str] = None,
):
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        logger.info("Recording match feedback from %s for %s", user_id, target_user_id)
        await service.record_match_feedback(user_id, target_user_id, rating, feedback_text)
        return {
            "message": "Match feedback recorded successfully",
            "user_id": user_id,
            "target_user_id": target_user_id,
            "rating": rating,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error recording match feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to record match feedback")
