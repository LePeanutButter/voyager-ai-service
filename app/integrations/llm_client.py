"""Unified async client for calling large language models (LLMs).

Purpose:
    Abstract HTTP transport to OpenAI-compatible or Ollama providers,
    and support ``none`` mode with no remote calls.

Responsibilities:
    Build chat messages, dispatch by provider, parse responses, and map failures
    to ``LLMUnavailableError`` for controlled degradation.

Dependencies:
    ``httpx`` (async client), ``app.core.config.settings`` for URL, model,
    temperature, and keys.

Configuration (environment / ``.env``):
    ``LLM_PROVIDER`` (``openai`` | ``ollama`` | ``none``), ``LLM_API_KEY``,
    ``LLM_BASE_URL``, ``LLM_MODEL``, ``LLM_MAX_TOKENS``, ``LLM_TEMPERATURE``.

Design note:
    Detailed prompt construction lives in ``app.prompts``; this module handles I/O only.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """The LLM backend is unavailable or returned an error."""


class LLMClient:
    """Async LLM client with provider selection from configuration.

    Important attributes:
        provider: Lowercase-normalized provider name.
        model: Remote model name.
        base_url: Base URL without trailing slash.
        api_key: Credential for OpenAI-style APIs.
        max_tokens: Output token limit.
        temperature: Sampling temperature.
    """

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER.lower()
        self.model = settings.LLM_MODEL
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def complete(
        self,
        system: str,
        user_message: str,
        extra_context: Optional[str] = None,
    ) -> Optional[str]:
        """Generates a completion for a single user message.

        Args:
            system: System prompt defining behavior.
            user_message: Latest user message.
            extra_context: Optional text injected as a prior ``assistant`` turn.

        Returns:
            Generated text, or ``None`` if provider is ``none`` (or per caller flow).

        Raises:
            LLMUnavailableError: On recoverable provider failures (may wrap generic errors).
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
        """Generates a completion from a full message history.

        Args:
            system: System prompt.
            messages: List of ``role`` / ``content`` dicts (user or assistant).

        Returns:
            Generated text or ``None`` if provider is ``none``.

        Raises:
            LLMUnavailableError: Network or provider API errors.
        """
        if self.provider == "none":
            return None

        full_messages = [{"role": "system", "content": system}] + messages
        return await self._dispatch(full_messages)

    # ------------------------------------------------------------------
    # Provider dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """Routes the request to the configured provider.

        Args:
            messages: Full sequence including system.

        Returns:
            Assistant message content or ``None`` if provider is unsupported.

        Raises:
            LLMUnavailableError: After HTTP, connection, or unexpected errors.
        """
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
        """Calls an OpenAI-compatible Chat Completions endpoint.

        Args:
            messages: API ``messages`` body.

        Returns:
            Text content of the first choice.

        Raises:
            LLMUnavailableError: Non-success HTTP status or connection failure.
        """
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
        """Calls the local Ollama Chat API.

        Args:
            messages: History for the ``/api/chat`` endpoint.

        Returns:
            Returned message content.

        Raises:
            LLMUnavailableError: HTTP or connection errors.
        """
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
        """Whether a real provider is configured and usable.

        Returns:
            ``True`` except in ``none`` mode; Ollama does not require an API key.
        """
        return self.provider != "none" and bool(self.api_key or self.provider == "ollama")
