"""
LLM Client abstraction layer.

Provides a unified async interface for calling Large Language Models,
with support for multiple providers (OpenAI-compatible, Ollama) and a
graceful "none" mode that falls through to the rule-based fallback.

Configuration (via environment / .env):
    LLM_PROVIDER   : "openai" | "ollama" | "none"   (default: "none")
    LLM_API_KEY    : API key for OpenAI-compatible providers
    LLM_BASE_URL   : Base URL (default: "https://api.openai.com/v1")
    LLM_MODEL      : Model name (default: "gpt-4o-mini")
    LLM_MAX_TOKENS : Max tokens in response (default: 1024)
    LLM_TEMPERATURE: Sampling temperature (default: 0.7)

Design decisions:
  - All I/O is async (httpx.AsyncClient) to match FastAPI's event loop.
  - Errors are caught and surfaced as LLMUnavailableError so callers
    can safely fall back to rule-based responses.
  - Prompt construction is delegated to the `prompts/` package; this
    class only handles transport and parsing.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the LLM backend is unreachable or returns an error."""


class LLMClient:
    """
    Async LLM client with provider abstraction.

    Usage:
        client = LLMClient()
        reply = await client.complete(
            system="You are a travel assistant.",
            user_message="Plan a trip to Tokyo."
        )
        # Falls back to None if provider == "none" or request fails.
    """

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def complete(
        self,
        system: str,
        user_message: str,
        extra_context: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a completion for a single user message.

        Args:
            system        : System prompt defining assistant behaviour.
            user_message  : The user's latest message.
            extra_context : Optional additional text injected as an
                            assistant-side context block before generation.

        Returns:
            Generated text string, or None if provider is "none" / call fails.
        """
        if self.provider == "none":
            return None

        messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
        if extra_context:
            messages.append({"role": "assistant", "content": extra_context})
        messages.append({"role": "user", "content": user_message})

        return await self._dispatch(messages)

    async def complete_with_history(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> Optional[str]:
        """
        Generate a completion given a full message history.

        Args:
            system   : System prompt.
            messages : List of {"role": "user"|"assistant", "content": str} dicts.

        Returns:
            Generated text string, or None if provider is "none" / call fails.
        """
        if self.provider == "none":
            return None

        full_messages = [{"role": "system", "content": system}] + messages
        return await self._dispatch(full_messages)

    # ------------------------------------------------------------------
    # Provider dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Route to the appropriate provider implementation."""
        try:
            if self.provider in ("openai", "openai_compatible"):
                return await self._call_openai_compatible(messages)
            elif self.provider == "ollama":
                return await self._call_ollama(messages)
            else:
                logger.warning(
                    "LLM provider '%s' is not supported. Returning None.", self.provider
                )
                return None
        except LLMUnavailableError:
            raise
        except Exception as exc:
            logger.error("Unexpected error calling LLM: %s", exc, exc_info=True)
            raise LLMUnavailableError(str(exc)) from exc

    async def _call_openai_compatible(
        self, messages: List[Dict[str, str]]
    ) -> Optional[str]:
        """Call an OpenAI-compatible Chat Completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "OpenAI API error %s: %s", exc.response.status_code, exc.response.text
                )
                raise LLMUnavailableError(
                    f"OpenAI API returned {exc.response.status_code}"
                ) from exc
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.error("LLM connection error: %s", exc)
                raise LLMUnavailableError("Cannot reach LLM provider") from exc

    async def _call_ollama(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Call a local Ollama Chat API endpoint."""
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"].strip()
            except httpx.HTTPStatusError as exc:
                logger.error("Ollama API error %s: %s", exc.response.status_code, exc.response.text)
                raise LLMUnavailableError(
                    f"Ollama API returned {exc.response.status_code}"
                ) from exc
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.error("Ollama connection error: %s", exc)
                raise LLMUnavailableError("Cannot reach Ollama") from exc

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if a real LLM provider is configured."""
        return self.provider != "none" and bool(self.api_key or self.provider == "ollama")
