"""
Chat feature package — AI Travel Chatbot.

Components:
  schemas.py              — ChatRequest / ChatResponse / TravelContext / Suggestion
  memory.py               — Per-user in-memory ConversationMemory
  context_extractor.py    — Rule-based intent & context extraction from user messages
  recommendation_engine.py — Budget/style/duration-aware structured recommendations
  proactive_engine.py     — Rule-based proactive suggestion triggers
  service.py              — ChatService orchestrator (uses all of the above)
  router.py               — FastAPI router exposing POST /chat and history endpoints
"""
