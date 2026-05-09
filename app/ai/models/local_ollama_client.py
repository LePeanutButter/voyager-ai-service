"""Local LLM inference client (Ollama only, no cloud providers)."""

from __future__ import annotations

import logging
from typing import Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LocalOllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_URL.rstrip("/")
        self.model = settings.LOCAL_MODEL_NAME

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False}
        read_s = max(30.0, float(settings.OLLAMA_HTTP_TIMEOUT_SECONDS))
        timeout = httpx.Timeout(connect=30.0, read=read_s, write=60.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return str(content).strip()
        except httpx.ConnectError as exc:
            logger.warning("Ollama no alcanzable en %s: %s", self.base_url, exc)
            return (
                "No hay conexión con Ollama (servicio LLM local). "
                f"Arranca Ollama en {self.base_url}, luego ejecuta en terminal: "
                f"`ollama pull {self.model}` y vuelve a intentar. "
                f"(Detalle técnico: {exc})"
            )
        except httpx.HTTPStatusError as exc:
            body = (exc.response.text or "")[:400]
            logger.warning("Ollama HTTP %s: %s", exc.response.status_code, body)
            return (
                f"Ollama respondió con error HTTP {exc.response.status_code}. "
                "Comprueba que el modelo existe (`ollama list`) y que coincide con "
                f"LOCAL_MODEL_NAME={self.model!r}. Cuerpo: {body}"
            )
        except httpx.TimeoutException as exc:
            logger.warning("Ollama timeout: %s", exc)
            return (
                "La respuesta de Ollama tardó demasiado (timeout). "
                "Prueba con un modelo más pequeño o aumenta el tiempo de espera en el servidor."
            )
        except Exception as exc:
            logger.exception("Error inesperado llamando a Ollama")
            return f"No se pudo generar la respuesta con el LLM local: {exc}"
