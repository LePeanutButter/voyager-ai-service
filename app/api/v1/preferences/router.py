"""REST endpoints for the adaptive travel preference questionnaire."""

from __future__ import annotations

import logging

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


@router.post(
    "/questionnaire/step",
    response_model=QuestionnaireStepResponse,
    summary="Adaptive questionnaire step",
)
async def questionnaire_step(
    body: QuestionnaireStepRequest,
    service: PreferenceQuestionnaireServiceDep,
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
)
async def questionnaire_submit(
    body: QuestionnaireSubmitRequest,
    service: PreferenceQuestionnaireServiceDep,
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
