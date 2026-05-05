"""Integration adapters for external systems or offline modes.

Responsibilities:
    - Abstract LLM providers and HTTP transport (`llm_client`).
    - Provide deterministic responses when no LLM is available (`fallback`).

Dependencies:
    `httpx`, configuration in `app.core.config`, chat schemas in
    `app.modules.chat.schemas`.
"""
