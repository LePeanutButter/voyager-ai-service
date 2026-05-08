"""SQLite-backed conversational memory for local chatbot."""

from __future__ import annotations

import json
from typing import Dict, List

from sqlalchemy import desc, select

from app.database.ai_sqlite import AIMessage, AISession, AISessionLocal, now_utc


class AIMemoryRepository:
    """Read/write chat sessions and messages in local SQLite."""

    def ensure_session(self, session_id: str, user_id: str) -> None:
        with AISessionLocal() as db:
            existing = db.scalar(select(AISession).where(AISession.session_id == session_id))
            if existing:
                existing.updated_at = now_utc()
            else:
                db.add(
                    AISession(
                        session_id=session_id,
                        user_id=user_id,
                        created_at=now_utc(),
                        updated_at=now_utc(),
                    )
                )
            db.commit()

    def add_message(self, session_id: str, role: str, content: str, embedding: List[float] | None) -> None:
        with AISessionLocal() as db:
            db.add(
                AIMessage(
                    session_id=session_id,
                    role=role,
                    content=content,
                    embedding_json=json.dumps(embedding) if embedding is not None else None,
                    created_at=now_utc(),
                )
            )
            sess = db.scalar(select(AISession).where(AISession.session_id == session_id))
            if sess:
                sess.updated_at = now_utc()
            db.commit()

    def get_recent_messages(self, session_id: str, limit: int = 12) -> List[Dict[str, str]]:
        with AISessionLocal() as db:
            rows = db.scalars(
                select(AIMessage)
                .where(AIMessage.session_id == session_id)
                .order_by(desc(AIMessage.created_at))
                .limit(limit)
            ).all()
            rows = list(reversed(rows))
            return [{"role": r.role, "content": r.content} for r in rows]
