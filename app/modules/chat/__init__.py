"""Conversational travel planning chat assisted by rules and optional LLM.

Main components:
    Schemas (`schemas`), per-user memory (`memory`), context extraction
    (`context_extractor`), suggestion engine (`recommendation_engine`),
    proactive hints (`proactive_engine`), orchestrator (`service`), and HTTP router
    in `app.api.v1.chat.router`.

Dependencies:
    `app.integrations` (LLM and fallback), `app.core.config`.
"""
