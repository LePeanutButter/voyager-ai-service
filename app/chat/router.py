"""
Chat API router — FastAPI endpoints for the AI Travel Chatbot.

Endpoints:
  POST   /api/v1/chat                        — Send a message, get a reply
  GET    /api/v1/chat/{userId}/history       — Retrieve conversation history
  DELETE /api/v1/chat/{userId}/history       — Clear conversation history

Authentication: None (handled externally by API gateway / backend).
Rate limiting: Not implemented here; apply at the gateway layer.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ClearHistoryResponse,
    ConversationHistoryResponse,
)
from app.chat.service import ChatService

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency injection — ChatService singleton
# ---------------------------------------------------------------------------

def get_chat_service(request: Request) -> ChatService:
    """
    Retrieve the ChatService singleton stored on application state.

    The singleton is attached during startup in main.py (lifespan).
    This approach avoids re-instantiating the service (and its in-memory
    conversation store) on every request.
    """
    service: ChatService = getattr(request.app.state, "chat_service", None)
    if service is None:
        # Should never happen after startup, but fail gracefully
        logger.error("ChatService not initialised on app.state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is not yet initialised. Please try again shortly.",
        )
    return service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the travel chatbot",
    description=(
        "Send a conversational message and receive an AI-powered travel planning reply. "
        "The chatbot maintains context across multiple turns per user. "
        "Context (destination, budget, duration, style) is extracted automatically from the message."
    ),
    responses={
        200: {"description": "Successful chat response with reply and suggestions"},
        400: {"description": "Invalid request (empty message or userId)"},
        503: {"description": "Chat service unavailable"},
    },
)
async def chat(
    request_data: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Main chat endpoint.

    - **userId**: Unique identifier for the user (string, required)
    - **message**: The user's conversational message (1–2000 chars, required)

    Returns a `ChatResponse` containing:
    - **reply**: Natural-language response from the assistant
    - **suggestions**: Structured activity/destination suggestions
    - **metadata**: Intent classification, context summary, turn number
    """
    try:
        logger.info(
            "Chat request — user=%s, message_len=%d",
            request_data.userId, len(request_data.message),
        )
        response = await service.handle_message(request_data)
        return response

    except ValueError as exc:
        logger.warning("Validation error in chat request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error processing chat request: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        )


@router.get(
    "/{userId}/history",
    response_model=ConversationHistoryResponse,
    summary="Get conversation history",
    description=(
        "Retrieve the full conversation history and accumulated travel context "
        "for a given user. Returns all messages in chronological order."
    ),
    responses={
        200: {"description": "Conversation history and context"},
        404: {"description": "No conversation history found for this user"},
    },
)
async def get_history(
    userId: str,
    service: ChatService = Depends(get_chat_service),
) -> ConversationHistoryResponse:
    """
    Get conversation history for a user.

    - **userId**: The user's unique identifier
    """
    if not userId or not userId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="userId must not be blank",
        )

    try:
        history_response = service.get_history(userId.strip())

        if history_response.total_messages == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conversation history found for user '{userId}'",
            )

        return history_response

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching history for user %s: %s", userId, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation history.",
        )


@router.delete(
    "/{userId}/history",
    response_model=ClearHistoryResponse,
    summary="Clear conversation history",
    description=(
        "Delete all conversation history and travel context for a given user. "
        "The next message from this user will start a fresh conversation."
    ),
    responses={
        200: {"description": "History cleared successfully"},
        404: {"description": "No conversation history found for this user"},
    },
)
async def clear_history(
    userId: str,
    service: ChatService = Depends(get_chat_service),
) -> ClearHistoryResponse:
    """
    Clear conversation history for a user.

    - **userId**: The user's unique identifier
    """
    if not userId or not userId.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="userId must not be blank",
        )

    try:
        cleared = await service.clear_history(userId.strip())

        if not cleared:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conversation history found for user '{userId}'",
            )

        logger.info("Cleared conversation history for user %s", userId)
        return ClearHistoryResponse(
            userId=userId.strip(),
            message=f"Conversation history for user '{userId}' has been cleared.",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error clearing history for user %s: %s", userId, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear conversation history.",
        )
