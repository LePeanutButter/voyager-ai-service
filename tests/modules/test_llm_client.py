import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.llm_client import LLMClient, LLMUnavailableError


@pytest.mark.asyncio
async def test_complete_none_provider(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "none", raising=False)
    c = LLMClient()
    r = await c.complete("s", "u")
    assert r is None


@pytest.mark.asyncio
async def test_complete_with_extra_context_none_provider(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "none", raising=False)
    c = LLMClient()
    r = await c.complete("s", "u", extra_context="ctx")
    assert r is None


@pytest.mark.asyncio
async def test_complete_with_history_none(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "none", raising=False)
    c = LLMClient()
    r = await c.complete_with_history("s", [{"role": "user", "content": "a"}])
    assert r is None


@pytest.mark.asyncio
async def test_unsupported_provider(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "weird", raising=False)
    c = LLMClient()
    c.provider = "weird"
    r = await c._dispatch([{"role": "user", "content": "x"}])
    assert r is None


@pytest.mark.asyncio
async def test_openai_http_error_raises():
    import httpx

    c = LLMClient()
    c.provider = "openai"
    c.api_key = "x"
    c.base_url = "https://api.openai.com/v1"

    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    err_resp = httpx.Response(500, request=req)
    err_resp.raise_for_status = lambda: (_ for _ in ()).throw(
        httpx.HTTPStatusError("500", request=req, response=err_resp)
    )

    async def _fake_post(*a, **kw):
        return err_resp

    class _CM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *x):
            return None

        post = staticmethod(_fake_post)

    with patch("app.integrations.llm_client.httpx.AsyncClient", return_value=_CM()):
        with pytest.raises(LLMUnavailableError):
            await c._call_openai_compatible([{"role": "user", "content": "a"}])


@pytest.mark.asyncio
async def test_openai_success():
    import httpx

    c = LLMClient()
    c.provider = "openai"
    c.api_key = "k"
    c.base_url = "https://api.openai.com/v1"

    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.json = MagicMock(
        return_value={"choices": [{"message": {"content": "  Hello  "}}]}
    )

    class _CM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *x):
            return None

        post = AsyncMock(return_value=ok)

    with patch("app.integrations.llm_client.httpx.AsyncClient", return_value=_CM()):
        out = await c._call_openai_compatible([{"role": "user", "content": "a"}])
    assert out == "Hello"


@pytest.mark.asyncio
async def test_openai_connect_error():
    import httpx

    c = LLMClient()
    c.provider = "openai"
    c.api_key = "k"
    c.base_url = "https://api.openai.com/v1"

    class _CM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *x):
            return None

        post = AsyncMock(side_effect=httpx.ConnectError("down", request=MagicMock()))

    with patch("app.integrations.llm_client.httpx.AsyncClient", return_value=_CM()):
        with pytest.raises(LLMUnavailableError, match="Cannot reach"):
            await c._call_openai_compatible([{"role": "user", "content": "a"}])


@pytest.mark.asyncio
async def test_ollama_success():
    c = LLMClient()
    c.provider = "ollama"
    c.base_url = "http://localhost:11434"
    c.model = "llama"

    ok = MagicMock()
    ok.raise_for_status = MagicMock()
    ok.json = MagicMock(return_value={"message": {"content": "  OK  "}})

    class _CM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *x):
            return None

        post = AsyncMock(return_value=ok)

    with patch("app.integrations.llm_client.httpx.AsyncClient", return_value=_CM()):
        out = await c._call_ollama([{"role": "user", "content": "a"}])
    assert out == "OK"


@pytest.mark.asyncio
async def test_ollama_http_error():
    import httpx

    c = LLMClient()
    c.provider = "ollama"
    c.base_url = "http://localhost:11434"

    req = httpx.Request("POST", "http://localhost:11434/api/chat")
    err_resp = httpx.Response(503, request=req)
    err_resp.raise_for_status = lambda: (_ for _ in ()).throw(
        httpx.HTTPStatusError("503", request=req, response=err_resp)
    )

    class _CM:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *x):
            return None

        post = AsyncMock(return_value=err_resp)

    with patch("app.integrations.llm_client.httpx.AsyncClient", return_value=_CM()):
        with pytest.raises(LLMUnavailableError):
            await c._call_ollama([{"role": "user", "content": "a"}])


@pytest.mark.asyncio
async def test_dispatch_wraps_generic_exception():
    c = LLMClient()
    c.provider = "openai"

    async def boom(*a, **k):
        raise RuntimeError("x")

    with patch.object(c, "_call_openai_compatible", boom):
        with pytest.raises(LLMUnavailableError, match="x"):
            await c._dispatch([{"role": "user", "content": "a"}])


@pytest.mark.asyncio
async def test_dispatch_reraises_llm_unavailable():
    c = LLMClient()
    c.provider = "openai"

    async def reraise(*a, **k):
        raise LLMUnavailableError("up")

    with patch.object(c, "_call_openai_compatible", reraise):
        with pytest.raises(LLMUnavailableError, match="up"):
            await c._dispatch([{"role": "user", "content": "a"}])


def test_is_available_openai_with_key(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "openai", raising=False)
    monkeypatch.setattr(config.settings, "LLM_API_KEY", "sk-test", raising=False)
    c = LLMClient()
    assert c.is_available() is True


def test_is_available_ollama_without_key(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "ollama", raising=False)
    monkeypatch.setattr(config.settings, "LLM_API_KEY", "", raising=False)
    c = LLMClient()
    assert c.is_available() is True


def test_is_available_none(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "none", raising=False)
    c = LLMClient()
    assert c.is_available() is False
