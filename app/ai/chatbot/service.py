"""Spanish local chatbot orchestrator (SQLite memory + local model + real recommendations)."""

from __future__ import annotations

from typing import Dict, List

from app.ai.embeddings.local_embeddings import LocalEmbeddingService
from app.ai.memory.repository import AIMemoryRepository
from app.ai.models.local_ollama_client import LocalOllamaClient


class LocalSpanishChatbotService:
    def __init__(self) -> None:
        self.memory = AIMemoryRepository()
        self.embedder = LocalEmbeddingService()
        self.llm = LocalOllamaClient()

    async def chat(self, user_id: str, session_id: str, message: str) -> Dict[str, object]:
        self.memory.ensure_session(session_id=session_id, user_id=user_id)
        user_embedding = self.embedder.embed(message)
        self.memory.add_message(session_id, "user", message, user_embedding)

        history = self.memory.get_recent_messages(session_id, limit=10)
        wants_recommendations = any(k in message.lower() for k in ("recom", "suger", "producto", "comprar"))

        recommendation_snippet = ""
        if wants_recommendations:
            recommendation_snippet = (
                "No hay candidatos en esta solicitud de chat. "
                "Envia candidatos reales en /api/v1/local/recommendations para obtener ranking."
            )

        system_prompt = (
            "Eres un asistente de IA local para usuarios hispanohablantes. "
            "Responde siempre en español natural, concreto y profesional. "
            "No inventes datos que no existan en el contexto. "
            "Si hay recomendaciones, intégralas con justificación breve."
        )
        prompt = self._build_user_prompt(message, history, recommendation_snippet)
        assistant_text = await self.llm.generate(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        )

        self.memory.add_message(
            session_id=session_id,
            role="assistant",
            content=assistant_text,
            embedding=self.embedder.embed(assistant_text),
        )
        return {
            "session_id": session_id,
            "reply": assistant_text,
            "used_recommendations": wants_recommendations,
            "recommendations": [],
        }

    def history(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        return self.memory.get_recent_messages(session_id=session_id, limit=limit)

    def _build_user_prompt(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        recommendation_snippet: str,
    ) -> str:
        context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-6:]])
        return (
            "Contexto reciente:\n"
            f"{context}\n\n"
            "Recomendaciones calculadas en IA local:\n"
            f"{recommendation_snippet}\n\n"
            "Mensaje actual del usuario:\n"
            f"{user_message}\n\n"
            "Responde en español."
        )
