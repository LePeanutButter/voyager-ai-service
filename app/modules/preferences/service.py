"""Session-backed orchestration for the adaptive preference questionnaire.

Purpose:
    Manage in-memory sessions, merge answers with the branching engine, and
    build the aggregated profile on submit.

Responsibilities:
    Create/resume sessions, run ``process_step`` and ``submit``, map answers to
    ``PreferenceProfilePayload``.

Dependencies:
    ``AdaptiveQuestionnaireEngine``, Pydantic schemas in ``schemas``.
"""

from __future__ import annotations

import logging
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.modules.preferences.engine import AdaptiveQuestionnaireEngine
from app.modules.preferences.schemas import (
    AnswerItem,
    PreferenceProfilePayload,
    QuestionnaireStepRequest,
    QuestionnaireStepResponse,
    QuestionnaireSubmitRequest,
    QuestionnaireSubmitResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class _Session:
    """Internal mutable state for one questionnaire run."""

    session_id: str
    user_id: str
    answers: Dict[str, List[str]] = field(default_factory=dict)
    step_index: int = 0


class PreferenceQuestionnaireService:
    """Coordinates questionnaire steps and final profile assembly.

    Uses in-memory sessions (fine for single-instance or dev; use Redis in production).

    Attributes:
        _sessions: Map of session_id to ``_Session``.
        _engine: Rule engine that selects the next questions.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, _Session] = {}
        self._engine = AdaptiveQuestionnaireEngine()

    def _new_session(self, user_id: str) -> _Session:
        """Creates and registers a new session for the user.

        Args:
            user_id: External user identifier.

        Returns:
            Fresh ``_Session`` with generated ``session_id``.
        """
        sid = str(uuid.uuid4())
        sess = _Session(session_id=sid, user_id=user_id)
        self._sessions[sid] = sess
        logger.info("Created preference questionnaire session %s for user %s", sid, user_id)
        return sess

    def _get_session(self, session_id: str) -> Optional[_Session]:
        """Looks up a session by id, if still present."""
        return self._sessions.get(session_id)

    @staticmethod
    def _first_answer(answers: Dict[str, List[str]], key: str) -> Optional[str]:
        return (answers.get(key) or [None])[0]

    def _apply_adventure_profile(
        self, answers: Dict[str, List[str]], categories: List[str], interests: List[str]
    ) -> str:
        categories.extend(["adventure", "outdoor"])
        adventure_intensity = self._first_answer(answers, "adventure_intensity")
        nature_focus = self._first_answer(answers, "nature_focus")
        if adventure_intensity:
            interests.append(f"adventure_intensity:{adventure_intensity}")
        if nature_focus:
            interests.append(f"nature_focus:{nature_focus}")
            if nature_focus == "mostly_nature":
                categories.append("nature")
        return "active"

    def _apply_cultural_profile(
        self, answers: Dict[str, List[str]], categories: List[str], interests: List[str]
    ) -> Optional[str]:
        categories.extend(["cultural", "urban"])
        culture_depth = self._first_answer(answers, "culture_depth")
        cultural_pace = self._first_answer(answers, "cultural_pace")
        if culture_depth:
            interests.append(f"culture_depth:{culture_depth}")
        if cultural_pace:
            interests.append(f"cultural_pace:{cultural_pace}")
            return cultural_pace.replace("_pace", "").replace("balanced", "balanced")
        return None

    def _apply_relax_profile(
        self, answers: Dict[str, List[str]], categories: List[str], interests: List[str]
    ) -> str:
        categories.extend(["relaxation", "wellness"])
        relax_setting = self._first_answer(answers, "relax_setting")
        social_energy = self._first_answer(answers, "social_energy")
        if relax_setting:
            interests.append(f"relax_setting:{relax_setting}")
        if social_energy:
            interests.append(f"social_energy:{social_energy}")
        return "slow"

    async def process_step(self, body: QuestionnaireStepRequest) -> QuestionnaireStepResponse:
        """Applies answers for one step and returns the next questions or completion.

        Args:
            body: User id, optional session id, and answers for this step.

        Returns:
            ``QuestionnaireStepResponse`` with updated session and questions.

        Raises:
            ValueError: Unknown session, user mismatch, or invalid session id.
        """
        if body.session_id:
            sess = self._get_session(body.session_id)
            if not sess:
                logger.warning("Unknown session_id=%s", body.session_id)
                raise ValueError("Invalid or expired session_id")
            if sess.user_id != body.user_id:
                raise ValueError("session_id does not belong to this user_id")
        else:
            sess = self._new_session(body.user_id)

        sess.answers = self._engine.merge_answers(sess.answers, body.answers)

        questions, complete, derived = self._engine.next_questions(sess.answers)
        step_before = sess.step_index
        if not complete:
            sess.step_index += 1

        await asyncio.sleep(0)
        message = None
        if not questions and complete:
            message = "Cuestionario completo"
        return QuestionnaireStepResponse(
            session_id=sess.session_id,
            step_index=step_before,
            is_complete=complete,
            derived_primary_category=derived,
            questions=questions,
            message=message,
        )

    def _build_profile(self, answers: Dict[str, List[str]]) -> tuple[str, PreferenceProfilePayload, str]:
        """Derives primary category, structured profile, and text summary from answers.

        Args:
            answers: Merged question_id → selected option ids.

        Returns:
            Tuple of (primary_category, payload, ai_context_summary).
        """
        primary = self._first_answer(answers, "primary_travel_style") or "unknown"
        categories: List[str] = []
        interests: List[str] = []
        pace: Optional[str] = None
        comfort = self._first_answer(answers, "trip_budget_band")

        if primary == "adventure":
            pace = self._apply_adventure_profile(answers, categories, interests)
        elif primary == "cultural":
            pace = self._apply_cultural_profile(answers, categories, interests)
        elif primary == "relax":
            pace = self._apply_relax_profile(answers, categories, interests)

        payload = PreferenceProfilePayload(
            travel_categories=sorted(set(categories)),
            pace=pace,
            interests=interests,
            comfort_level=comfort,
            notes_for_ai=None,
        )

        summary = (
            f"Primary style={primary}. "
            f"Categories={payload.travel_categories}. "
            f"Signals={interests}. "
            f"Budget_band={comfort or 'unspecified'}."
        )
        return primary, payload, summary

    async def submit(self, body: QuestionnaireSubmitRequest) -> QuestionnaireSubmitResponse:
        """Validates completion and returns the final profile for the session.

        Args:
            body: User, session, and final answers.

        Returns:
            ``QuestionnaireSubmitResponse`` with profile and summary.

        Raises:
            ValueError: Invalid session, user mismatch, or questionnaire incomplete.
        """
        sess = self._get_session(body.session_id)
        if not sess:
            raise ValueError("Invalid or expired session_id")
        if sess.user_id != body.user_id:
            raise ValueError("session_id does not belong to this user_id")

        sess.answers = self._engine.merge_answers(sess.answers, body.answers)
        complete_answers = sess.answers
        _questions, is_done, _ = self._engine.next_questions(complete_answers)
        if not is_done or _questions:
            raise ValueError("Questionnaire is not complete yet; call /step until is_complete is true")

        primary, profile, summary = self._build_profile(dict(complete_answers))
        profile.notes_for_ai = summary

        await asyncio.sleep(0)
        logger.info(
            "Preference questionnaire submitted user=%s session=%s primary=%s",
            body.user_id,
            body.session_id,
            primary,
        )

        return QuestionnaireSubmitResponse(
            user_id=body.user_id,
            session_id=body.session_id,
            primary_category=primary,
            preference_profile=profile,
            ai_context_summary=summary,
        )
