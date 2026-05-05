"""HTTP router for traveler matching and weight learning.

Responsibilities:
    Partner search, compatibility, connections, feedback, and outcomes
    to adjust the matching model.

Dependencies:
    `MatchingServiceDep`, schemas in `app.modules.matching.schemas`.
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
    """Finds compatible candidates from request criteria.

    Args:
        request_data: Source user and matching filters.
        service: `MatchingService`.

    Returns:
        Ranked match list.

    Raises:
        HTTPException: 500 on matching engine error.
    """
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
    """Computes compatibility score or breakdown between two users.

    Args:
        user_id: First user.
        target_user_id: Second user.
        service: `MatchingService`.

    Returns:
        Compatibility object from the service.

    Raises:
        HTTPException: 404 if a profile is missing; 500 on internal error.
    """
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
    """Starts a connection request between two travelers.

    Args:
        service: `MatchingService`.
        user_id: Initiating user.
        target_user_id: Target user.
        message: Optional request text.

    Returns:
        Confirmation with `connection_id` when the service provides it.

    Raises:
        HTTPException: 500 on internal error.
    """
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
    """Lists the user's connections, optionally filtered by status.

    Args:
        user_id: Queried user.
        service: `MatchingService`.
        status: Optional textual status filter.

    Returns:
        Dict with `connections` and `total_count`.

    Raises:
        HTTPException: 500 on internal error.
    """
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
    """Accepts or declines an existing connection request.

    Args:
        connection_id: Request identifier.
        response: Literal `accept` or `decline`.
        service: `MatchingService`.
        message: Optional reply to the other user.

    Returns:
        Confirmation with updated status.

    Raises:
        HTTPException: 400 if `response` is invalid; 404 if not found; 500 on failure.
    """
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
    """Suggests travel buddies by location and limits.

    Args:
        user_id: User to recommend for.
        service: `MatchingService`.
        location: Optional geographic filter.
        limit: Max suggestions.

    Returns:
        Dict with recommendation list and count.

    Raises:
        HTTPException: 500 on internal error.
    """
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
    """Records a connection outcome to update learning weights.

    Args:
        body: Users, outcome, and optional dimensional snapshot.
        service: `MatchingService`.

    Returns:
        Status and updated weights when applicable.

    Raises:
        HTTPException: 500 on persist or compute error.
    """
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
    """Records explicit rating for the match or interaction.

    Args:
        user_id: Rater.
        target_user_id: Counterparty.
        service: `MatchingService`.
        rating: Integer 1–5.
        feedback_text: Optional free-text comment.

    Returns:
        Confirmation with ids and rating.

    Raises:
        HTTPException: 400 if rating is out of range; 500 on internal error.
    """
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
