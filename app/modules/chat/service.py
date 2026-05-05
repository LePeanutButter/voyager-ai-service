"""
ChatService — central orchestrator for the travel chatbot.

Coordinates the full request/response pipeline:
  1. Load existing conversation memory
  2. Extract intent and context from the user message
  3. Update memory with new message + context
  4. Generate structured suggestions (recommendation engine)
  5. Evaluate proactive triggers
  6. Generate a natural-language reply (LLM or rule-based fallback)
  7. Store assistant reply in memory
  8. Return ChatResponse

Design:
  - All I/O is async; synchronous sub-components (extractor, engines)
    are called directly in the event loop (no CPU-intensive work).
  - Defensive: every stage has try/except so partial failures degrade
    gracefully rather than crashing the endpoint.
  - Singleton-friendly: ChatService owns or holds references to shared
    in-memory components (including ConversationMemory) and is intended
    to be created once and reused across requests, not instantiated
    per-request.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.modules.chat.context_extractor import ContextExtractor
from app.modules.chat.memory import ConversationMemory
from app.modules.chat.proactive_engine import ProactiveEngine
from app.modules.chat.recommendation_engine import ChatRecommendationEngine
from app.modules.chat.schemas import (
    ChatIntent,
    ChatRequest,
    ChatResponse,
    ConversationMessage,
    Suggestion,
    TravelContext,
)
from app.core.config import settings
from app.integrations import fallback as rule_based
from app.integrations.llm_client import LLMClient, LLMUnavailableError
from app.prompts import budget_adjustment as budget_prompt
from app.prompts import follow_up_context as follow_up_prompt
from app.prompts import travel_planning as planning_prompt

logger = logging.getLogger(__name__)

# Maximum recent messages passed to LLM for multi-turn context
_LLM_HISTORY_WINDOW = 10


class ChatService:
    """
    Travel chatbot orchestrator.

    Intended to be used as a long-lived singleton (shared across requests)
    since it holds references to shared in-memory components.
    """

    def __init__(self) -> None:
        self.memory = ConversationMemory()
        self.extractor = ContextExtractor()
        self.rec_engine = ChatRecommendationEngine()
        self.proactive_engine = ProactiveEngine()
        self.llm_client = LLMClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_message(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user message and return a chat response.

        Args:
            request: Validated ChatRequest (userId + message).

        Returns:
            ChatResponse with reply, suggestions, and metadata.
        """
        user_id = request.userId
        message = request.message.strip()

        logger.info("Processing message for user %s (%d chars)", user_id, len(message))

        # ── Step 1: Classify intent + extract context from message ─────
        intent, partial_context = self._safe_extract(message)

        # ── Step 2: Read current session state ─────────────────────────
        is_first = self.memory.is_first_message(user_id)
        old_budget = self.memory.get_context(user_id).budget_usd

        # ── Step 3: Store user message in history ──────────────────────
        user_msg = ConversationMessage(role="user", content=message, intent=intent)
        await self.memory.add_message(user_id, user_msg)

        # ── Step 4: Merge extracted context into session ────────────────
        await self.memory.update_context(user_id, partial_context)
        context = self.memory.get_context(user_id)

        # ── Step 5: Generate structured suggestions ─────────────────────
        suggestions = self._generate_suggestions(context, intent)

        # ── Step 6: Evaluate proactive triggers ─────────────────────────
        history = self.memory.get_messages(user_id)
        proactive = self._safe_proactive(context, history)
        all_suggestions = suggestions + proactive

        # ── Step 7: Generate natural-language reply ──────────────────────
        reply, llm_used = await self._generate_reply(
            intent=intent,
            message=message,
            context=context,
            suggestions=suggestions,
            history=history,
            is_first=is_first,
            old_budget=old_budget,
        )

        # ── Step 8: Store assistant reply ───────────────────────────────
        assistant_msg = ConversationMessage(role="assistant", content=reply)
        await self.memory.add_message(user_id, assistant_msg)

        # ── Step 9: Build metadata ──────────────────────────────────────
        metadata = self._build_metadata(
            intent=intent,
            context=context,
            llm_used=llm_used,
            message_number=self.memory.message_count(user_id),
        )

        logger.info(
            "Reply generated for user %s (intent=%s, suggestions=%d, proactive=%d)",
            user_id, intent.value, len(suggestions), len(proactive),
        )

        return ChatResponse(
            reply=reply,
            suggestions=all_suggestions,
            metadata=metadata,
        )

    def get_history(self, user_id: str):
        """Return the full conversation history and context for a user."""
        from app.modules.chat.schemas import ConversationHistoryResponse

        messages = self.memory.get_messages(user_id)
        context = self.memory.get_context(user_id)
        return ConversationHistoryResponse(
            userId=user_id,
            messages=messages,
            context=context,
            total_messages=len(messages),
        )

    async def clear_history(self, user_id: str) -> bool:
        """Clear conversation history for a user. Returns True if found."""
        return await self.memory.clear(user_id)

    # ------------------------------------------------------------------
    # Private pipeline steps
    # ------------------------------------------------------------------

    def _safe_extract(self, message: str):
        """Extract intent and context, returning defaults on any error."""
        try:
            return self.extractor.extract(message)
        except Exception as exc:
            logger.warning("Context extraction failed: %s", exc, exc_info=True)
            return ChatIntent.UNKNOWN, TravelContext()

    def _generate_suggestions(
        self, context: TravelContext, intent: ChatIntent
    ) -> List[Suggestion]:
        """Generate structured suggestions based on context and intent."""
        try:
            if intent == ChatIntent.GREETING:
                return []  # No suggestions on a greeting
            
            # Scale suggestions based on duration (approx 2 per day)
            # but cap at the global maximum from settings
            max_suggs = settings.CHAT_MAX_SUGGESTIONS
            if context.duration_days and context.duration_days > 0:
                max_suggs = min(context.duration_days * 2, max_suggs)
            else:
                max_suggs = min(5, max_suggs)  # Default fallback if no duration

            # If user asked about specific activity types, filter to those
            if intent == ChatIntent.ACTIVITY_QUERY and context.activity_types:
                return self.rec_engine.generate_for_activity_types(
                    context=context,
                    max_suggestions=max_suggs,
                )

            # General planning / follow-up
            if (context.destination or context.budget_usd or context.travel_style or 
                context.interests or context.activity_types):
                return self.rec_engine.generate(context, max_suggestions=max_suggs)

            return []
        except Exception as exc:
            logger.warning("Suggestion generation failed: %s", exc, exc_info=True)
            return []

    def _safe_proactive(
        self, context: TravelContext, history: List[ConversationMessage]
    ) -> List[Suggestion]:
        """Run proactive engine, returning empty list on any error."""
        try:
            return self.proactive_engine.evaluate(context, history)
        except Exception as exc:
            logger.warning("Proactive engine failed: %s", exc, exc_info=True)
            return []

    async def _generate_reply(
        self,
        intent: ChatIntent,
        message: str,
        context: TravelContext,
        suggestions: List[Suggestion],
        history: List[ConversationMessage],
        is_first: bool,
        old_budget: Optional[float],
    ) -> Tuple[str, bool]:
        """
        Generate the natural-language reply.

        Tries the LLM first (if configured); falls back to rule-based on any failure.

        Returns:
            (reply_text, llm_used) — llm_used is True when the LLM produced the reply.
        """
        # Handle greeting without LLM
        if intent == ChatIntent.GREETING:
            return rule_based.build_greeting_reply(), False

        # --- LLM path (skip if provider == "none") ---
        if self.llm_client.is_available():
            try:
                llm_reply = await self._call_llm(intent, message, context, history, old_budget)
                if llm_reply:
                    return llm_reply, True
            except LLMUnavailableError as exc:
                logger.warning("LLM unavailable, falling back to rule-based: %s", exc)
            except Exception as exc:
                logger.error("Unexpected LLM error, falling back: %s", exc, exc_info=True)

        # --- Rule-based fallback path ---
        return self._rule_based_reply(
            intent=intent,
            message=message,
            context=context,
            suggestions=suggestions,
            is_first=is_first,
            old_budget=old_budget,
        ), False

    async def _call_llm(
        self,
        intent: ChatIntent,
        message: str,
        context: TravelContext,
        history: List[ConversationMessage],
        old_budget: Optional[float],
    ) -> Optional[str]:
        """Call the LLM with the appropriate prompt for the given intent."""
        recent_history = history[-_LLM_HISTORY_WINDOW:]
        history_dicts = [{"role": m.role, "content": m.content} for m in recent_history]

        # Budget adjustment — use specialised prompt
        if intent == ChatIntent.BUDGET_QUESTION and context.budget_usd is not None:
            system = budget_prompt.SYSTEM_PROMPT
            user_prompt = budget_prompt.render_budget_adjustment_prompt(
                user_message=message,
                context=context,
                old_budget_usd=old_budget,
                new_budget_usd=context.budget_usd,
            )
            return await self.llm_client.complete(system=system, user_message=user_prompt)

        # Multi-turn follow-up — inject history when prior messages exist
        if history_dicts:
            system = follow_up_prompt.SYSTEM_PROMPT
            from app.modules.chat.schemas import ConversationMessage as CM

            # Exclude the latest user message from history to avoid duplicating
            # it: the user_prompt already embeds the message under
            # "## Latest User Message".
            follow_up_history_dicts = history_dicts
            if (
                follow_up_history_dicts
                and follow_up_history_dicts[-1]["role"] == "user"
                and follow_up_history_dicts[-1]["content"] == message
            ):
                follow_up_history_dicts = follow_up_history_dicts[:-1]

            user_prompt = follow_up_prompt.render_follow_up_prompt(
                user_message=message,
                context=context,
                recent_history=[CM(**m) for m in [{"role": h["role"], "content": h["content"]}
                                                    for h in follow_up_history_dicts]],
            )
            return await self.llm_client.complete_with_history(
                system=system,
                messages=follow_up_history_dicts + [{"role": "user", "content": user_prompt}],
            )

        # Initial planning message
        system = planning_prompt.SYSTEM_PROMPT
        user_prompt = planning_prompt.render_planning_prompt(
            user_message=message,
            context=context,
        )
        return await self.llm_client.complete(system=system, user_message=user_prompt)

    def _rule_based_reply(
        self,
        intent: ChatIntent,
        message: str,
        context: TravelContext,
        suggestions: List[Suggestion],
        is_first: bool,
        old_budget: Optional[float],
    ) -> str:
        """Generate a reply using the rule-based fallback system."""
        if intent == ChatIntent.BUDGET_QUESTION and context.budget_usd is not None:
            return rule_based.build_budget_reply(
                context=context,
                suggestions=suggestions,
                old_budget=old_budget,
            )

        if intent in (ChatIntent.TRAVEL_PLANNING, ChatIntent.DESTINATION_QUERY):
            return rule_based.build_planning_reply(
                context=context,
                suggestions=suggestions,
            )

        if intent == ChatIntent.ACTIVITY_QUERY:
            return rule_based.build_follow_up_reply(
                context=context,
                suggestions=suggestions,
                user_message=message,
            )

        # FOLLOW_UP, CLARIFICATION, UNKNOWN → generic contextual reply
        return rule_based.build_follow_up_reply(
            context=context,
            suggestions=suggestions,
            user_message=message,
        )

    def _build_metadata(
        self,
        intent: ChatIntent,
        context: TravelContext,
        llm_used: bool,
        message_number: int,
    ) -> dict:
        """Build the metadata dict for the API response."""
        return {
            "intent": intent.value,
            "llm_used": llm_used,
            "message_number": message_number,
            "context_summary": {
                "destination": context.destination,
                "budget_usd": context.budget_usd,
                "duration_days": context.duration_days,
                "travel_style": context.travel_style,
                "group_size": context.group_size,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
