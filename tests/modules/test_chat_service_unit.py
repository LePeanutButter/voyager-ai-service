"""Unit tests for ChatService (mocked LLM)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.chat.schemas import ChatIntent, ChatRequest, ConversationMessage, TravelContext
from app.modules.chat.service import ChatService


@pytest.fixture
def svc(monkeypatch):
    """ChatService with LLM disabled."""
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "none", raising=False)
    s = ChatService()
    return s


@pytest.mark.asyncio
async def test_handle_greeting(svc):
    req = ChatRequest(userId="u_chat_1", message="Hello!")
    resp = await svc.handle_message(req)
    assert resp.reply
    assert resp.metadata["intent"] == ChatIntent.GREETING.value


@pytest.mark.asyncio
async def test_handle_planning_rule_based(svc):
    req = ChatRequest(userId="u_chat_2", message="Plan a trip to Rome with $900 budget")
    resp = await svc.handle_message(req)
    assert resp.reply
    assert isinstance(resp.suggestions, list)


@pytest.mark.asyncio
async def test_generate_suggestions_greeting_empty(svc):
    assert svc._generate_suggestions(TravelContext(), ChatIntent.GREETING) == []


@pytest.mark.asyncio
async def test_safe_proactive_error_returns_empty(monkeypatch, svc):
    monkeypatch.setattr(svc.proactive_engine, "evaluate", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    assert svc._safe_proactive(TravelContext(), []) == []


@pytest.mark.asyncio
async def test_llm_path_fallback_on_none(monkeypatch, svc):
    monkeypatch.setattr(svc.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(svc.llm_client, "complete", AsyncMock(return_value=None))

    req = ChatRequest(userId="u_chat_3", message="I want to visit Paris")
    resp = await svc.handle_message(req)
    assert resp.metadata["llm_used"] is False


@pytest.mark.asyncio
async def test_llm_success(monkeypatch, svc):
    monkeypatch.setattr(svc.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(svc.llm_client, "complete", AsyncMock(return_value="LLM says hi"))
    monkeypatch.setattr(
        svc.llm_client, "complete_with_history", AsyncMock(return_value="LLM says hi")
    )

    req = ChatRequest(userId="u_chat_4", message="Tell me about Tokyo museums")
    resp = await svc.handle_message(req)
    assert resp.reply == "LLM says hi"
    assert resp.metadata["llm_used"] is True


@pytest.mark.asyncio
async def test_call_llm_budget_question_branch(monkeypatch, svc):
    monkeypatch.setattr(svc.llm_client, "is_available", lambda: True)
    monkeypatch.setattr(svc.llm_client, "complete", AsyncMock(return_value="budget text"))

    ctx = TravelContext(budget_usd=500.0)
    out = await svc._call_llm(
        ChatIntent.BUDGET_QUESTION, "how much", ctx, [], old_budget=400.0
    )
    assert out == "budget text"


@pytest.mark.asyncio
async def test_get_history_and_clear(svc):
    await svc.handle_message(ChatRequest(userId="u_hist", message="Hi"))
    h = svc.get_history("u_hist")
    assert h.total_messages >= 1
    assert await svc.clear_history("u_hist") is True
