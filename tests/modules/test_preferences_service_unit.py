"""Unit tests for PreferenceQuestionnaireService."""

import pytest

from app.modules.preferences.schemas import (
    AnswerItem,
    QuestionnaireStepRequest,
    QuestionnaireSubmitRequest,
)
from app.modules.preferences.service import PreferenceQuestionnaireService


@pytest.fixture
def pq():
    return PreferenceQuestionnaireService()


@pytest.mark.asyncio
async def test_process_step_new_session(pq):
    body = QuestionnaireStepRequest(user_id="u_pq", answers=[])
    r = await pq.process_step(body)
    assert r.session_id and not r.is_complete


@pytest.mark.asyncio
async def test_process_step_invalid_session(pq):
    body = QuestionnaireStepRequest(
        user_id="u_pq",
        session_id="00000000-0000-0000-0000-000000000000",
        answers=[],
    )
    with pytest.raises(ValueError, match="Invalid"):
        await pq.process_step(body)


@pytest.mark.asyncio
async def test_process_step_wrong_user(pq):
    body1 = QuestionnaireStepRequest(user_id="u_a", answers=[])
    r = await pq.process_step(body1)
    body2 = QuestionnaireStepRequest(
        user_id="other",
        session_id=r.session_id,
        answers=[AnswerItem(question_id="primary_travel_style", selected_option_ids=["adventure"])],
    )
    with pytest.raises(ValueError, match="does not belong"):
        await pq.process_step(body2)


@pytest.mark.asyncio
async def test_submit_complete_adventure(pq):
    # Drive engine to completion for adventure path
    r0 = await pq.process_step(QuestionnaireStepRequest(user_id="u_sub", answers=[]))
    r1 = await pq.process_step(
        QuestionnaireStepRequest(
            user_id="u_sub",
            session_id=r0.session_id,
            answers=[AnswerItem(question_id="primary_travel_style", selected_option_ids=["adventure"])],
        )
    )
    assert not r1.is_complete
    r2 = await pq.process_step(
        QuestionnaireStepRequest(
            user_id="u_sub",
            session_id=r0.session_id,
            answers=[
                AnswerItem(question_id="adventure_intensity", selected_option_ids=["moderate"]),
                AnswerItem(question_id="nature_focus", selected_option_ids=["mostly_nature"]),
            ],
        )
    )
    assert not r2.is_complete
    r3 = await pq.process_step(
        QuestionnaireStepRequest(
            user_id="u_sub",
            session_id=r0.session_id,
            answers=[AnswerItem(question_id="trip_budget_band", selected_option_ids=["mid"])],
        )
    )
    assert r3.is_complete

    out = await pq.submit(
        QuestionnaireSubmitRequest(user_id="u_sub", session_id=r0.session_id, answers=[])
    )
    assert out.primary_category == "adventure"
    assert out.preference_profile.travel_categories


@pytest.mark.asyncio
async def test_submit_not_complete_raises(pq):
    r0 = await pq.process_step(QuestionnaireStepRequest(user_id="u_inc", answers=[]))
    with pytest.raises(ValueError, match="not complete"):
        await pq.submit(
            QuestionnaireSubmitRequest(user_id="u_inc", session_id=r0.session_id, answers=[])
        )


@pytest.mark.asyncio
async def test_build_profile_cultural_and_relax(pq):
    _, payload_c, _ = pq._build_profile(
        {
            "primary_travel_style": ["cultural"],
            "culture_depth": ["museums"],
            "cultural_pace": ["balanced_pace"],
            "trip_budget_band": ["mid"],
        }
    )
    assert "cultural" in payload_c.travel_categories

    _, payload_r, _ = pq._build_profile(
        {
            "primary_travel_style": ["relax"],
            "relax_setting": ["beach"],
            "social_energy": ["quiet"],
            "trip_budget_band": ["budget"],
        }
    )
    assert "relaxation" in payload_r.travel_categories
