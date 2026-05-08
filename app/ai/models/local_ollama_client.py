"""Local LLM inference client (Ollama only, no cloud providers)."""

from __future__ import annotations

from typing import Dict, List

import httpx

from app.core.config import settings


class LocalOllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_URL.rstrip("/")
        self.model = settings.LOCAL_MODEL_NAME

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return str(content).strip()
