"""REST endpoints for the adaptive travel preference questionnaire."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.preferences.schemas import (
    QuestionnaireStepRequest,
    QuestionnaireStepResponse,
    QuestionnaireSubmitRequest,
    QuestionnaireSubmitResponse,
)
from app.preferences.service import PreferenceQuestionnaireService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_preference_service(request: Request) -> PreferenceQuestionnaireService:
    service: PreferenceQuestionnaireService | None = getattr(
        request.app.state, "preference_questionnaire_service", None
    )
    if service is None:
        logger.error("PreferenceQuestionnaireService not initialised on app.state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preference questionnaire service is unavailable",
        )
    return service


@router.post(
    "/questionnaire/step",
    response_model=QuestionnaireStepResponse,
    summary="Adaptive questionnaire step",
    description=(
        "Returns the next question set based on previous answers. "
        "Omit session_id on the first call; reuse session_id on subsequent calls."
    ),
)
async def questionnaire_step(
    body: QuestionnaireStepRequest,
    service: Annotated[PreferenceQuestionnaireService, Depends(get_preference_service)],
) -> QuestionnaireStepResponse:
    try:
        return await service.process_step(body)
    except ValueError as exc:
        logger.warning("Validation error in questionnaire step: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in questionnaire step")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process questionnaire step",
        ) from exc


@router.post(
    "/questionnaire/submit",
    response_model=QuestionnaireSubmitResponse,
    summary="Submit completed questionnaire",
    description=(
        "Call after is_complete is true from /step. "
        "Produces a structured preference profile and summary string for the AI engine."
    ),
)
async def questionnaire_submit(
    body: QuestionnaireSubmitRequest,
    service: Annotated[PreferenceQuestionnaireService, Depends(get_preference_service)],
) -> QuestionnaireSubmitResponse:
    try:
        return await service.submit(body)
    except ValueError as exc:
        logger.warning("Validation error in questionnaire submit: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in questionnaire submit")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit questionnaire",
        ) from exc
