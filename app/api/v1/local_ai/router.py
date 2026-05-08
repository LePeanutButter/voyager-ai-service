"""Endpoints for local chatbot and AI-local recommendations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.api.v1.local_ai.schemas import (
    LocalChatRequest,
    LocalChatResponse,
    RecommendationRequest,
    RecommendationResponse,
)

router = APIRouter()


@router.post(
    "/chat/message",
    response_model=LocalChatResponse,
    responses={500: {"description": "Error en chatbot local"}},
)
async def local_chat_message(req: LocalChatRequest, request: Request):
    svc = request.app.state.local_chatbot_service
    try:
        out = await svc.chat(user_id=req.user_id, session_id=req.session_id, message=req.message)
        return LocalChatResponse(**out)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en chatbot local: {exc}") from exc


@router.get("/chat/history/{session_id}")
async def local_chat_history(session_id: str, request: Request, limit: int = 20):
    svc = request.app.state.local_chatbot_service
    return {"session_id": session_id, "messages": svc.history(session_id=session_id, limit=limit)}


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    responses={
        400: {"description": "Datos inválidos para recomendar"},
        500: {"description": "Error interno de recomendaciones"},
    },
)
async def local_real_recommendations(req: RecommendationRequest, request: Request):
    svc = request.app.state.real_recommendation_service
    try:
        data = svc.recommend(
            user_id=req.user_id,
            query_text=req.query,
            candidates=[c.model_dump() for c in req.candidates],
            limit=req.limit,
        )
        return RecommendationResponse(**data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en recomendaciones: {exc}") from exc


@router.post(
    "/recommendations/feedback",
    responses={
        400: {"description": "Rating debe estar entre 1 y 5"},
        500: {"description": "Error interno de feedback"},
    },
)
async def local_recommendation_feedback(
    user_id: str,
    item_id: str,
    rating: int,
    request: Request,
):
    svc = request.app.state.real_recommendation_service
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
    try:
        svc.record_feedback(user_id=user_id, item_id=item_id, rating=rating)
        return {
            "message": "Feedback recorded successfully",
            "user_id": user_id,
            "item_id": item_id,
            "rating": rating,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en feedback: {exc}") from exc
