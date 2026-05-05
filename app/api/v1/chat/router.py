"""
Chat API router — AI Travel Chatbot.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ChatServiceDep
from app.modules.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ClearHistoryResponse,
    ConversationHistoryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    summary="Send a message to the travel chatbot",
    responses={
        200: {"description": "Successful chat response with reply and suggestions"},
        422: {"description": "Validation error (missing/invalid userId or message)"},
        503: {"description": "Chat service unavailable"},
    },
)
async def chat(
    request_data: ChatRequest,
    service: ChatServiceDep,
) -> ChatResponse:
    try:
        logger.info(
            "Chat request — user=%s, message_len=%d",
            request_data.userId,
            len(request_data.message),
        )
        return await service.handle_message(request_data)
    except ValueError as exc:
        logger.warning("Validation error in chat request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected error processing chat request: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )


@router.get(
    "/{user_id}/history",
    summary="Get conversation history",
    responses={
        200: {"description": "Conversation history and context"},
        404: {"description": "No conversation history found for this user"},
    },
)
async def get_history(user_id: str, service: ChatServiceDep) -> ConversationHistoryResponse:
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id must not be blank")
    try:
        history_response = service.get_history(user_id.strip())
        if history_response.total_messages == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No conversation history found for this user",
            )
        return history_response
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation history.",
        )


@router.delete(
    "/{user_id}/history",
    summary="Clear conversation history",
    responses={
        200: {"description": "History cleared successfully"},
        404: {"description": "No conversation history found for this user"},
    },
)
async def clear_history(user_id: str, service: ChatServiceDep) -> ClearHistoryResponse:
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id must not be blank")
    try:
        cleared = await service.clear_history(user_id.strip())
        if not cleared:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No conversation history found for this user",
            )
        logger.info("Cleared conversation history successfully.")
        return ClearHistoryResponse(
            userId=user_id.strip(),
            message="Conversation history has been cleared.",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error clearing history: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear conversation history.",
        )
