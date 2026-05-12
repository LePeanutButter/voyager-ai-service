from app.modules.preferences.engine import AdaptiveQuestionnaireEngine
from app.modules.preferences.schemas import AnswerItem


def test_merge_and_next():
    eng = AdaptiveQuestionnaireEngine()
    answers = eng.merge_answers(
        {},
        [AnswerItem(question_id="primary_travel_style", selected_option_ids=["relax"])],
    )
    q, done, primary = eng.next_questions(answers)
    assert done is False
    assert primary == "relax"
