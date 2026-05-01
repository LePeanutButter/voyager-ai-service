"""
Prompts package — structured prompt templates for the travel chatbot.

Each module exposes a single render_*() function that returns a
fully-formed prompt string ready for injection into an LLM call.

Templates:
  travel_planning.py   — main system + initial planning prompt
  budget_adjustment.py — prompt for budget-aware response generation
  follow_up_context.py — prompt for multi-turn context continuation
"""
