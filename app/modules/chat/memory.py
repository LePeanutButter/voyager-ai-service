"""
In-memory conversation memory store.

Provides per-user storage for:
  - Message history (role + content + timestamp)
  - Accumulated TravelContext (destination, budget, duration, style…)

Design principles:
  - Thread-safe via asyncio.Lock (one lock per user session)
  - Bounded history: oldest messages are evicted when the cap is reached
  - Zero external dependencies (no Redis, no DB) — easily swapped out
    by replacing ConversationMemory with a Redis-backed implementation
    that exposes the same async interface.

Extensibility hook:
  - Subclass ConversationMemory and override _persist() / _load() to add
    Redis or DB-backed persistence without touching the rest of the stack.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import desc, select

from app.db import database as db_database
from app.db.runtime_models import ChatMessageRecord, ChatSessionRecord
from app.modules.chat.schemas import ConversationMessage, TravelContext
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserSession:
    """Holds all state for a single user's conversation."""

    def __init__(self, user_id: str, max_history: int) -> None:
        self.user_id = user_id
        self.max_history = max_history
        self.messages: List[ConversationMessage] = []
        self.context: TravelContext = TravelContext()
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)
        self._lock: asyncio.Lock = asyncio.Lock()

    async def add_message(self, message: ConversationMessage) -> None:
        """Append a message and evict oldest if cap is exceeded."""
        async with self._lock:
            self.messages.append(message)
            if len(self.messages) > self.max_history:
                self.messages = self.messages[-self.max_history:]
            self.updated_at = datetime.now(timezone.utc)

    async def update_context(self, partial_context: TravelContext) -> None:
        """Merge a partial context extraction into the session context."""
        async with self._lock:
            self.context = self.context.merge(partial_context)
            self.updated_at = datetime.now(timezone.utc)

    async def clear(self) -> None:
        """Reset the session to its initial empty state."""
        async with self._lock:
            self.messages = []
            self.context = TravelContext()
            self.updated_at = datetime.now(timezone.utc)

    def get_messages(self) -> List[ConversationMessage]:
        """Return a snapshot of the current message list (no lock needed for reads)."""
        return list(self.messages)

    def get_context(self) -> TravelContext:
        """Return a snapshot of the current travel context."""
        return self.context.model_copy()

    def message_count(self) -> int:
        return len(self.messages)


class ConversationMemory:
    """
    Global in-memory store for all user sessions.

    Usage:
        memory = ConversationMemory()  # typically a singleton via DI

        # Record a message
        await memory.add_message(user_id, ConversationMessage(role="user", content="..."))

        # Update context from extraction
        await memory.update_context(user_id, extracted_context)

        # Read history for LLM prompt construction
        history = memory.get_messages(user_id)
        context = memory.get_context(user_id)
    """

    def __init__(self) -> None:
        db_database.init_db_engine()
        self._sessions: Dict[str, UserSession] = {}
        self._global_lock: asyncio.Lock = asyncio.Lock()
        self._max_history: int = settings.CHAT_MAX_HISTORY

    @staticmethod
    def _db():
        assert db_database.SessionLocal is not None
        return db_database.SessionLocal()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_or_create_session(self, user_id: str) -> UserSession:
        """Return the existing session or create a new one (thread-safe)."""
        if user_id not in self._sessions:
            async with self._global_lock:
                # Double-checked locking pattern
                if user_id not in self._sessions:
                    logger.info("Creating new conversation session for user %s", user_id)
                    self._sessions[user_id] = UserSession(user_id, self._max_history)
                    with self._db() as db:
                        if db.get(ChatSessionRecord, user_id) is None:
                            db.add(
                                ChatSessionRecord(
                                    user_id=user_id,
                                    context_json=TravelContext().model_dump_json(),
                                    created_at=datetime.now(timezone.utc),
                                    updated_at=datetime.now(timezone.utc),
                                )
                            )
                            db.commit()
        return self._sessions[user_id]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def add_message(self, user_id: str, message: ConversationMessage) -> None:
        """Append a message to a user's session history."""
        session = await self._get_or_create_session(user_id)
        await session.add_message(message)
        with self._db() as db:
            db.add(
                ChatMessageRecord(
                    user_id=user_id,
                    role=message.role,
                    content=message.content,
                    intent=message.intent.value if message.intent else None,
                    timestamp=message.timestamp or datetime.now(timezone.utc),
                )
            )
            db.commit()
        logger.debug(
            "Added %s message for user %s (total: %d)",
            message.role, user_id, session.message_count()
        )

    async def update_context(self, user_id: str, partial_context: TravelContext) -> None:
        """Merge a newly extracted partial context into the user's session."""
        session = await self._get_or_create_session(user_id)
        await session.update_context(partial_context)
        with self._db() as db:
            row = db.get(ChatSessionRecord, user_id)
            if row:
                row.context_json = session.get_context().model_dump_json()
                row.updated_at = datetime.now(timezone.utc)
                db.commit()

    def get_messages(self, user_id: str, last_n: Optional[int] = None) -> List[ConversationMessage]:
        """
        Retrieve conversation history for a user.

        Args:
            user_id: User identifier.
            last_n : If provided, return only the last N messages.

        Returns:
            List of ConversationMessage in chronological order.
        """
        session = self._sessions.get(user_id)
        if session is None:
            with self._db() as db:
                rows = db.scalars(
                    select(ChatMessageRecord)
                    .where(ChatMessageRecord.user_id == user_id)
                    .order_by(desc(ChatMessageRecord.timestamp), desc(ChatMessageRecord.id))
                    .limit(last_n or self._max_history)
                ).all()
            rows = list(reversed(rows))
            return [
                ConversationMessage(role=r.role, content=r.content, timestamp=r.timestamp)
                for r in rows
            ]
        messages = session.get_messages()
        if last_n is not None:
            messages = messages[-last_n:]
        return messages

    def get_context(self, user_id: str) -> TravelContext:
        """Return the current TravelContext for a user (empty context if new user)."""
        session = self._sessions.get(user_id)
        if session is None:
            with self._db() as db:
                row = db.get(ChatSessionRecord, user_id)
                if not row:
                    return TravelContext()
                return TravelContext(**json.loads(row.context_json or "{}"))
        return session.get_context()

    def is_first_message(self, user_id: str) -> bool:
        """Return True if this user has no prior conversation history."""
        session = self._sessions.get(user_id)
        return session is None or session.message_count() == 0

    def message_count(self, user_id: str) -> int:
        """Return the number of messages in a user's history."""
        session = self._sessions.get(user_id)
        if session:
            return session.message_count()
        with self._db() as db:
            return len(
                db.scalars(
                    select(ChatMessageRecord.id).where(ChatMessageRecord.user_id == user_id)
                ).all()
            )

    async def clear(self, user_id: str) -> bool:
        """
        Clear a user's conversation history and context.

        Returns:
            True if the session existed and was cleared, False otherwise.
        """
        session = self._sessions.get(user_id)
        if session is not None:
            await session.clear()
        with self._db() as db:
            rows = db.scalars(
                select(ChatMessageRecord).where(ChatMessageRecord.user_id == user_id)
            ).all()
            for row in rows:
                db.delete(row)
            srow = db.get(ChatSessionRecord, user_id)
            if srow:
                srow.context_json = TravelContext().model_dump_json()
                srow.updated_at = datetime.now(timezone.utc)
            db.commit()
        logger.info("Cleared conversation history")
        return bool(session is not None)

    def active_session_count(self) -> int:
        """Return the number of active user sessions (for monitoring)."""
        return len(self._sessions)
