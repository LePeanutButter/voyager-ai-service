from app.modules.chat.schemas import TravelContext, ChatRequest


def test_travel_context_merge():
    a = TravelContext(destination="A", budget_usd=100)
    b = TravelContext(budget_usd=200, interests=["x"])
    m = a.merge(b)
    assert m.budget_usd == 200
    assert "x" in m.interests


def test_chat_request_validation():
    r = ChatRequest(userId="u1", message="  hi  ")
    assert r.message == "hi"
