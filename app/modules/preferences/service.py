"""Session-backed orchestration for the preference questionnaire."""

from __future__ import annotations

import logging
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
    session_id: str
    user_id: str
    answers: Dict[str, List[str]] = field(default_factory=dict)
    step_index: int = 0


class PreferenceQuestionnaireService:
    """In-memory sessions; suitable for single-instance or dev — swap for Redis in prod."""

    def __init__(self) -> None:
        self._sessions: Dict[str, _Session] = {}
        self._engine = AdaptiveQuestionnaireEngine()

    def _new_session(self, user_id: str) -> _Session:
        sid = str(uuid.uuid4())
        sess = _Session(session_id=sid, user_id=user_id)
        self._sessions[sid] = sess
        logger.info("Created preference questionnaire session %s for user %s", sid, user_id)
        return sess

    def _get_session(self, session_id: str) -> Optional[_Session]:
        return self._sessions.get(session_id)

    async def process_step(self, body: QuestionnaireStepRequest) -> QuestionnaireStepResponse:
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

        return QuestionnaireStepResponse(
            session_id=sess.session_id,
            step_index=step_before,
            is_complete=complete,
            derived_primary_category=derived,
            questions=questions,
            message=None if questions else ("Cuestionario completo" if complete else None),
        )

    def _build_profile(self, answers: Dict[str, List[str]]) -> tuple[str, PreferenceProfilePayload, str]:
        primary = (answers.get("primary_travel_style") or ["unknown"])[0]
        categories: List[str] = []
        interests: List[str] = []
        pace: Optional[str] = None
        comfort: Optional[str] = None

        budget = (answers.get("trip_budget_band") or [None])[0]
        if budget:
            comfort = budget

        if primary == "adventure":
            categories.extend(["adventure", "outdoor"])
            ai = (answers.get("adventure_intensity") or [None])[0]
            nf = (answers.get("nature_focus") or [None])[0]
            if ai:
                interests.append(f"adventure_intensity:{ai}")
            if nf:
                interests.append(f"nature_focus:{nf}")
                if nf == "mostly_nature":
                    categories.append("nature")
            pace = "active"
        elif primary == "cultural":
            categories.extend(["cultural", "urban"])
            cd = (answers.get("culture_depth") or [None])[0]
            cp = (answers.get("cultural_pace") or [None])[0]
            if cd:
                interests.append(f"culture_depth:{cd}")
            if cp:
                interests.append(f"cultural_pace:{cp}")
                pace = cp.replace("_pace", "").replace("balanced", "balanced")
        elif primary == "relax":
            categories.extend(["relaxation", "wellness"])
            rs = (answers.get("relax_setting") or [None])[0]
            se = (answers.get("social_energy") or [None])[0]
            if rs:
                interests.append(f"relax_setting:{rs}")
            if se:
                interests.append(f"social_energy:{se}")
            pace = "slow"

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
