"""Full branch coverage for AdaptiveQuestionnaireEngine."""

import pytest

from app.modules.preferences.engine import AdaptiveQuestionnaireEngine, PRIMARY
from app.modules.preferences.schemas import AnswerItem


@pytest.fixture
def eng():
    return AdaptiveQuestionnaireEngine()


def test_merge_answers(eng):
    m = eng.merge_answers(
        {"a": ["1"]},
        [AnswerItem(question_id="b", selected_option_ids=["2"])],
    )
    assert m["a"] == ["1"] and m["b"] == ["2"]


def test_next_primary_only(eng):
    q, done, cat = eng.next_questions({})
    assert not done and cat is None
    assert len(q) == 1 and q[0].id == PRIMARY.id


def test_adventure_flow(eng):
    a = {"primary_travel_style": ["adventure"]}
    q1, done1, _ = eng.next_questions(a)
    assert not done1 and len(q1) == 2

    a2 = {**a, "adventure_intensity": ["moderate"], "nature_focus": ["balanced_nc"]}
    q2, done2, _ = eng.next_questions(a2)
    assert not done2 and q2[0].id == "trip_budget_band"

    a3 = {**a2, "trip_budget_band": ["mid"]}
    q3, done3, cat = eng.next_questions(a3)
    assert done3 and cat == "adventure" and q3 == []


def test_cultural_flow(eng):
    a = {"primary_travel_style": ["cultural"]}
    q1, done1, _ = eng.next_questions(a)
    assert not done1 and len(q1) == 2

    a2 = {
        **a,
        "culture_depth": ["museums"],
        "cultural_pace": ["balanced_pace"],
    }
    q2, done2, _ = eng.next_questions(a2)
    assert not done2 and q2[0].id == "trip_budget_band"

    a3 = {**a2, "trip_budget_band": ["comfort"]}
    q3, done3, cat = eng.next_questions(a3)
    assert done3 and cat == "cultural"


def test_relax_flow(eng):
    a = {"primary_travel_style": ["relax"]}
    q1, done1, _ = eng.next_questions(a)
    assert not done1 and len(q1) == 2

    a2 = {**a, "relax_setting": ["beach"], "social_energy": ["quiet"]}
    q2, done2, _ = eng.next_questions(a2)
    assert not done2 and q2[0].id == "trip_budget_band"

    a3 = {**a2, "trip_budget_band": ["budget"]}
    _, done3, cat = eng.next_questions(a3)
    assert done3 and cat == "relax"


def test_derive_primary_invalid(eng):
    assert eng.derive_primary_category({"primary_travel_style": ["weird"]}) is None
