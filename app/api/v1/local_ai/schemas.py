"""Schemas for local AI/chat and real recommendation endpoints."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class LocalChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)


class LocalChatResponse(BaseModel):
    session_id: str
    reply: str
    used_recommendations: bool
    recommendations: List[dict]


class RecommendationRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=50)
    candidates: List["RecommendationCandidate"] = Field(
        min_length=1,
        description="Candidatos reales enviados por el cliente; no se usa catálogo interno.",
    )


class RecommendationCandidate(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=128)
    price: float = Field(default=0, ge=0)
    content_text: str = Field(default="", max_length=4000)


class RecommendationResponse(BaseModel):
    user: dict
    preferences: List[str]
    recent_interactions: List[dict]
    items: List[dict]
