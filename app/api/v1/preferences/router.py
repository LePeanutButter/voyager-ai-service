"""REST endpoints for the adaptive travel preference questionnaire.

Responsibilities:
    Step-by-step (`/questionnaire/step`) and final submit (`/questionnaire/submit`)
    over in-memory sessions managed by `PreferenceQuestionnaireService`.

Dependencies:
    `PreferenceQuestionnaireServiceDep`, schemas in `app.modules.preferences.schemas`.
"""

from __future__ import annotations

import logging
import inspect

from fastapi import APIRouter, HTTPException, status

from app.api.deps import PreferenceQuestionnaireServiceDep
from app.modules.preferences.schemas import (
    QuestionnaireStepRequest,
    QuestionnaireStepResponse,
    QuestionnaireSubmitRequest,
    QuestionnaireSubmitResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _resolve(value):
    if inspect.isawaitable(value):
        return await value
    return value


@router.post(
    "/questionnaire/step",
    summary="Adaptive questionnaire step",
)
async def questionnaire_step(
    body: QuestionnaireStepRequest,
    service: PreferenceQuestionnaireServiceDep,
) -> QuestionnaireStepResponse:
    """Processes one questionnaire step (creates session or advances questions).

    Args:
        body: User id, optional session id, and step answers.
        service: Questionnaire orchestrator.

    Returns:
        Next question block or questionnaire-complete flag.

    Raises:
        HTTPException: 400 on business `ValueError`; 500 on unexpected errors.
    """
    try:
        return await _resolve(service.process_step(body))
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
    summary="Submit completed questionnaire",
)
async def questionnaire_submit(
    body: QuestionnaireSubmitRequest,
    service: PreferenceQuestionnaireServiceDep,
) -> QuestionnaireSubmitResponse:
    """Closes the questionnaire and returns the aggregated profile when complete.

    Args:
        body: User, session, and final accumulated answers.
        service: Questionnaire orchestrator.

    Returns:
        AI-facing profile and text summary.

    Raises:
        HTTPException: 400 if incomplete or invalid session; 500 on other errors.
    """
    try:
        return await _resolve(service.submit(body))
    except ValueError as exc:
        logger.warning("Validation error in questionnaire submit: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in questionnaire submit")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit questionnaire",
        ) from exc
