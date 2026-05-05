"""Request and response models for the adaptive travel preference questionnaire."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


QuestionType = Literal["single_choice", "multi_choice"]


class QuestionOption(BaseModel):
    id: str
    label: str


class QuestionnaireQuestion(BaseModel):
    id: str
    prompt: str
    question_type: QuestionType
    options: List[QuestionOption] = Field(default_factory=list)


class AnswerItem(BaseModel):
    question_id: str
    selected_option_ids: List[str] = Field(default_factory=list)


class QuestionnaireStepRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=256)
    session_id: Optional[str] = None
    answers: List[AnswerItem] = Field(default_factory=list)


class QuestionnaireStepResponse(BaseModel):
    session_id: str
    step_index: int
    is_complete: bool
    derived_primary_category: Optional[str] = None
    questions: List[QuestionnaireQuestion] = Field(default_factory=list)
    message: Optional[str] = None


class PreferenceProfilePayload(BaseModel):
    travel_categories: List[str] = Field(default_factory=list)
    pace: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    comfort_level: Optional[str] = None
    notes_for_ai: Optional[str] = None


class QuestionnaireSubmitRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=256)
    session_id: str = Field(..., min_length=1)
    answers: List[AnswerItem] = Field(default_factory=list)


class QuestionnaireSubmitResponse(BaseModel):
    user_id: str
    session_id: str
    primary_category: str
    preference_profile: PreferenceProfilePayload
    ai_context_summary: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[dict] = None
