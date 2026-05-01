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
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.chat.schemas import ConversationMessage, TravelContext
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserSession:
    """Holds all state for a single user's conversation."""

    def __init__(self, user_id: str, max_history: int) -> None:
        self.user_id = user_id
        self.max_history = max_history
        self.messages: List[ConversationMessage] = []
        self.context: TravelContext = TravelContext()
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()
        self._lock: asyncio.Lock = asyncio.Lock()

    async def add_message(self, message: ConversationMessage) -> None:
        """Append a message and evict oldest if cap is exceeded."""
        async with self._lock:
            self.messages.append(message)
            if len(self.messages) > self.max_history:
                self.messages = self.messages[-self.max_history:]
            self.updated_at = datetime.utcnow()

    async def update_context(self, partial_context: TravelContext) -> None:
        """Merge a partial context extraction into the session context."""
        async with self._lock:
            self.context = self.context.merge(partial_context)
            self.updated_at = datetime.utcnow()

    async def clear(self) -> None:
        """Reset the session to its initial empty state."""
        async with self._lock:
            self.messages = []
            self.context = TravelContext()
            self.updated_at = datetime.utcnow()

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
        self._sessions: Dict[str, UserSession] = {}
        self._global_lock: asyncio.Lock = asyncio.Lock()
        self._max_history: int = settings.CHAT_MAX_HISTORY

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
        return self._sessions[user_id]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def add_message(self, user_id: str, message: ConversationMessage) -> None:
        """Append a message to a user's session history."""
        session = await self._get_or_create_session(user_id)
        await session.add_message(message)
        logger.debug(
            "Added %s message for user %s (total: %d)",
            message.role, user_id, session.message_count()
        )

    async def update_context(self, user_id: str, partial_context: TravelContext) -> None:
        """Merge a newly extracted partial context into the user's session."""
        session = await self._get_or_create_session(user_id)
        await session.update_context(partial_context)

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
            return []
        messages = session.get_messages()
        if last_n is not None:
            messages = messages[-last_n:]
        return messages

    def get_context(self, user_id: str) -> TravelContext:
        """Return the current TravelContext for a user (empty context if new user)."""
        session = self._sessions.get(user_id)
        if session is None:
            return TravelContext()
        return session.get_context()

    def is_first_message(self, user_id: str) -> bool:
        """Return True if this user has no prior conversation history."""
        session = self._sessions.get(user_id)
        return session is None or session.message_count() == 0

    def message_count(self, user_id: str) -> int:
        """Return the number of messages in a user's history."""
        session = self._sessions.get(user_id)
        return session.message_count() if session else 0

    async def clear(self, user_id: str) -> bool:
        """
        Clear a user's conversation history and context.

        Returns:
            True if the session existed and was cleared, False otherwise.
        """
        session = self._sessions.get(user_id)
        if session is None:
            return False
        await session.clear()
        logger.info("Cleared conversation history for user %s", user_id)
        return True

    def active_session_count(self) -> int:
        """Return the number of active user sessions (for monitoring)."""
        return len(self._sessions)
