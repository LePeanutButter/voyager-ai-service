"""Request and response models for the adaptive travel preference questionnaire.

Purpose:
    Type step/submit flows and the derived profile consumed by recommendation systems.

Dependencies:
    Pydantic ``BaseModel``, ``Field``, ``Literal``.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


QuestionType = Literal["single_choice", "multi_choice"]


class QuestionOption(BaseModel):
    """Selectable option shown for one questionnaire question."""

    id: str
    label: str


class QuestionnaireQuestion(BaseModel):
    """Single question block with type and options."""

    id: str
    prompt: str
    question_type: QuestionType
    options: List[QuestionOption] = Field(default_factory=list)


class AnswerItem(BaseModel):
    """User selections for one question in a step payload."""

    question_id: str
    selected_option_ids: List[str] = Field(default_factory=list)


class QuestionnaireStepRequest(BaseModel):
    """Advances or starts a questionnaire session."""

    user_id: str = Field(..., min_length=1, max_length=256)
    session_id: Optional[str] = None
    answers: List[AnswerItem] = Field(default_factory=list)


class QuestionnaireStepResponse(BaseModel):
    """Next questions or completion flag after a step."""

    session_id: str
    step_index: int
    is_complete: bool
    derived_primary_category: Optional[str] = None
    questions: List[QuestionnaireQuestion] = Field(default_factory=list)
    message: Optional[str] = None


class PreferenceProfilePayload(BaseModel):
    """Normalized profile extracted from answers for AI and recommendations."""

    travel_categories: List[str] = Field(default_factory=list)
    pace: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    comfort_level: Optional[str] = None
    notes_for_ai: Optional[str] = None


class QuestionnaireSubmitRequest(BaseModel):
    """Final submission with full answer set for a session."""

    user_id: str = Field(..., min_length=1, max_length=256)
    session_id: str = Field(..., min_length=1)
    answers: List[AnswerItem] = Field(default_factory=list)


class QuestionnaireSubmitResponse(BaseModel):
    """Closed questionnaire with primary category and profile summary."""

    user_id: str
    session_id: str
    primary_category: str
    preference_profile: PreferenceProfilePayload
    ai_context_summary: str


class ErrorResponse(BaseModel):
    """Standard error envelope for questionnaire failures."""

    error_code: str
    message: str
    details: Optional[dict] = None
