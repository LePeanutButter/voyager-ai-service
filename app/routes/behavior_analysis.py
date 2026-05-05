"""
Behavior Analysis API routes.

Endpoints for tracking user interactions and analyzing implicit behavior patterns
to automatically update user preferences and improve recommendations.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional
import logging

from app.models.schemas import (
    BehaviorTrackingRequest,
    BehaviorAnalysisRequest,
    ImplicitPreferenceUpdate,
    APIResponse
)
from app.services.behavior_analysis_service import BehaviorAnalysisService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_behavior_service(request: Request) -> BehaviorAnalysisService:
    """Dependency injection for behavior analysis service."""
    existing = getattr(request.app.state, "behavior_analysis_service", None)
    if existing is not None:
        return existing
    model_manager = getattr(request.app.state, "model_manager", None)
    request.app.state.behavior_analysis_service = BehaviorAnalysisService(model_manager)
    return request.app.state.behavior_analysis_service


@router.post("/track", response_model=APIResponse)
async def track_user_behavior(
    request: BehaviorTrackingRequest,
    service: BehaviorAnalysisService = Depends(get_behavior_service)
):
    """
    Track a user interaction for behavior analysis.
    
    - **user_id**: Unique identifier for the user
    - **interaction_type**: Type of interaction (view, click, bookmark, reject, etc.)
    - **activity_id**: Optional ID of the activity interacted with
    - **activity_category**: Optional category of the activity
    - **session_duration**: Optional duration of the session in seconds
    - **context**: Additional context information
    
    Tracks user interactions to build behavior patterns for implicit preference learning.
    """
    try:
        success = await service.track_interaction(request)
        
        if success:
            return APIResponse(
                success=True,
                message="Behavior tracked successfully",
                data={"tracked": True}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track behavior"
            )
            
    except Exception as e:
        logger.error(f"Error tracking behavior: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking behavior: {str(e)}"
        )


@router.post("/analyze", response_model=ImplicitPreferenceUpdate)
async def analyze_user_behavior(
    request: BehaviorAnalysisRequest,
    service: BehaviorAnalysisService = Depends(get_behavior_service)
):
    """
    Analyze user behavior patterns and generate preference updates.
    
    - **user_id**: Unique identifier for the user
    - **analysis_period_days**: Number of days to analyze (default: 7)
    - **include_patterns**: Whether to include detected patterns (default: True)
    - **include_preference_updates**: Whether to calculate preference updates (default: True)
    
    Analyzes user interactions over the specified period to detect patterns
    and calculate implicit preference updates.
    """
    try:
        result = await service.analyze_behavior(request)
        logger.info(f"Behavior analysis completed for user {request.user_id}")
        return result
        
    except ValueError as e:
        logger.error(f"Invalid analysis request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error analyzing behavior: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing behavior: {str(e)}"
        )


@router.get("/summary/{user_id}")
async def get_behavior_summary(
    user_id: str,
    days: int = 30,
    service: BehaviorAnalysisService = Depends(get_behavior_service)
):
    """
    Get a summary of user's behavior patterns.
    
    - **user_id**: Unique identifier for the user
    - **days**: Number of days to analyze (default: 30)
    
    Returns a comprehensive summary of the user's behavior patterns,
    interaction statistics, and detected preferences.
    """
    try:
        summary = await service.get_user_behavior_summary(user_id, days)
        
        if "error" in summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=summary["error"]
            )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting behavior summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting behavior summary: {str(e)}"
        )


@router.post("/batch-track", response_model=APIResponse)
async def batch_track_behavior(
    requests: List[BehaviorTrackingRequest],
    service: BehaviorAnalysisService = Depends(get_behavior_service)
):
    """
    Track multiple user interactions in a batch.
    
    - **requests**: List of behavior tracking requests
    
    Efficiently tracks multiple interactions for batch processing scenarios.
    """
    try:
        success_count = 0
        failed_count = 0
        
        for request in requests:
            success = await service.track_interaction(request)
            if success:
                success_count += 1
            else:
                failed_count += 1
        
        return APIResponse(
            success=True,
            message=f"Batch tracking completed: {success_count} successful, {failed_count} failed",
            data={
                "successful": success_count,
                "failed": failed_count,
                "total": len(requests)
            }
        )
        
    except Exception as e:
        logger.error(f"Error in batch tracking: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in batch tracking: {str(e)}"
        )


@router.get("/patterns/{user_id}")
async def get_detected_patterns(
    user_id: str,
    days: int = 7,
    service: BehaviorAnalysisService = Depends(get_behavior_service)
):
    """
    Get detected behavior patterns for a user.
    
    - **user_id**: Unique identifier for the user
    - **days**: Number of days to analyze (default: 7)
    
    Returns only the detected behavior patterns without preference updates.
    """
    try:
        # Create analysis request with patterns only
        request = BehaviorAnalysisRequest(
            user_id=user_id,
            analysis_period_days=days,
            include_patterns=True,
            include_preference_updates=False
        )
        
        result = await service.analyze_behavior(request)
        
        return {
            "user_id": user_id,
            "analysis_period": result.analysis_period.dict(),
            "patterns": [pattern.dict() for pattern in result.detected_patterns],
            "confidence_score": result.confidence_score
        }
        
    except ValueError as e:
        logger.error(f"Invalid pattern request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting patterns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting patterns: {str(e)}"
        )


@router.delete("/clear/{user_id}", response_model=APIResponse)
async def clear_user_behavior_data(
    user_id: str,
    service: BehaviorAnalysisService = Depends(get_behavior_service)
):
    """
    Clear all behavior data for a user.
    
    - **user_id**: Unique identifier for the user
    
    Removes all stored behavior data for the specified user.
    Use with caution - this will reset all learned preferences.
    """
    try:
        if hasattr(service, 'behavior_data') and user_id in service.behavior_data:
            del service.behavior_data[user_id]
            
            return APIResponse(
                success=True,
                message="Behavior data cleared successfully",
                data={"cleared": True}
            )
        else:
            return APIResponse(
                success=True,
                message="No behavior data found to clear",
                data={"cleared": False}
            )
            
    except Exception as e:
        logger.error(f"Error clearing behavior data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error clearing behavior data: {str(e)}"
        )
