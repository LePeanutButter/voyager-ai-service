"""
Proactive Recommendation Engine.

Implements rule-based triggers that surface unsolicited but contextually
relevant suggestions during a conversation. These triggers observe patterns
across the accumulated TravelContext and message history.

Design philosophy:
  - Rules are explicit, readable, and individually toggleable
  - Each trigger returns a Suggestion with is_proactive=True so the UI
    can present it differently (e.g., as a "💡 Tip" card)
  - Triggers are checked AFTER every user message; the cheapest checks
    run first (fail-fast)
  - No ML — all decisions are deterministic and auditable
  - Extendable: add new ProactiveTrigger subclasses without modifying
    the engine's orchestration logic

Current triggers:
  1. RepeatedTopicTrigger  — keyword mentioned ≥2 times → suggest that activity
  2. SoonTripTrigger       — trip within 7 days → send a "start packing" reminder
  3. NoBudgetTrigger       — 3+ messages without a budget → prompt for budget
  4. NoDestinationTrigger  — 3+ messages without a destination → prompt
  5. LongTripTrigger       — duration > 14 days → suggest multi-city structure
  6. SoloTravelerTrigger   — solo traveller → suggest social/group activities
  7. FamilyTrigger         — family group → highlight kid-friendly activities
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app.chat.schemas import ConversationMessage, Suggestion, TravelContext

logger = logging.getLogger(__name__)

# Minimum threshold for keyword-frequency trigger
_KEYWORD_REPEAT_THRESHOLD = 2

# Budget missing after this many messages → prompt
_BUDGET_PROMPT_AFTER = 3

# Destination missing after this many messages → prompt
_DESTINATION_PROMPT_AFTER = 3


class ProactiveEngine:
    """
    Evaluates rule-based triggers and returns proactive Suggestion objects.

    Usage:
        engine = ProactiveEngine()
        proactive = engine.evaluate(context, history)
        # Returns 0..N Suggestion objects with is_proactive=True
    """

    def evaluate(
        self,
        context: TravelContext,
        history: List[ConversationMessage],
    ) -> List[Suggestion]:
        """
        Evaluate all triggers and return any proactive suggestions.

        Args:
            context : Current accumulated travel context.
            history : Full conversation history for this user.

        Returns:
            List of proactive Suggestion objects (may be empty).
        """
        results: List[Suggestion] = []
        user_message_count = sum(1 for m in history if m.role == "user")

        # Run triggers in priority order (cheapest / highest value first)
        triggers = [
            self._check_repeated_topic(context),
            self._check_soon_trip(context),
            self._check_no_budget(context, user_message_count),
            self._check_no_destination(context, user_message_count),
            self._check_long_trip(context),
            self._check_solo_social(context),
            self._check_family_friendly(context),
        ]

        for suggestion in triggers:
            if suggestion is not None:
                results.append(suggestion)

        if results:
            logger.debug(
                "ProactiveEngine surfaced %d suggestion(s) for context (dest=%s)",
                len(results), context.destination,
            )

        return results

    # ------------------------------------------------------------------
    # Individual triggers
    # ------------------------------------------------------------------

    def _check_repeated_topic(self, context: TravelContext) -> Optional[Suggestion]:
        """
        Trigger: A keyword has been mentioned ≥ THRESHOLD times.

        Example: user mentions "mountain" twice → suggest hiking.
        """
        if not context.keyword_counts:
            return None

        top_keyword, count = max(context.keyword_counts.items(), key=lambda kv: kv[1])
        if count < _KEYWORD_REPEAT_THRESHOLD:
            return None

        # Map keyword to a specific activity suggestion
        activity_map = {
            "mountain": ("Adventure Hiking", "adventure",
                         f"You've mentioned mountains a lot — have you considered a guided mountain hike"
                         f"{' near ' + context.destination if context.destination else ''}?"),
            "food":     ("Culinary Tour", "dining",
                         "Your love of food is clear! A local food tour or cooking class would be perfect."),
            "beach":    ("Beach Day", "relaxation",
                         f"{'The beaches near ' + context.destination if context.destination else 'Beaches'}"
                         " are definitely worth a dedicated day."),
            "museum":   ("Museum Pass", "cultural",
                         "A multi-day museum pass could save you money and time."),
            "history":  ("Heritage Walk", "cultural",
                         "A guided heritage walk would be a great way to explore the historical side."),
            "shopping": ("Local Markets", "shopping",
                         "Local markets offer the best authentic finds at budget-friendly prices."),
            "nature":   ("Nature Excursion", "adventure",
                         f"A guided nature excursion"
                         f"{' around ' + context.destination if context.destination else ''}"
                         " would fit perfectly with your interests."),
        }

        if top_keyword in activity_map:
            name, act_type, description = activity_map[top_keyword]
            return Suggestion(
                name=name,
                activity_type=act_type,
                description=description,
                is_proactive=True,
                tags=["recommended", "based-on-interests"],
            )

        return None

    def _check_soon_trip(self, context: TravelContext) -> Optional[Suggestion]:
        """
        Trigger: Trip start date is within 7 days of today.
        Surfaces a "your trip is soon" reminder with logistics tips.
        """
        if not context.start_date:
            return None

        try:
            start = datetime.fromisoformat(context.start_date)
            days_until = (start.date() - datetime.utcnow().date()).days
            if 0 <= days_until <= 7:
                return Suggestion(
                    name="⏰ Your Trip Is Coming Up Soon!",
                    activity_type="sightseeing",
                    description=(
                        f"Your trip starts in {days_until} day{'s' if days_until != 1 else ''}! "
                        "Make sure to: confirm all reservations, download offline maps, "
                        "notify your bank, and pack weather-appropriate clothing."
                    ),
                    is_proactive=True,
                    tags=["reminder", "logistics"],
                )
        except (ValueError, TypeError):
            pass  # Malformed date — skip this trigger

        return None

    def _check_no_budget(
        self, context: TravelContext, user_message_count: int
    ) -> Optional[Suggestion]:
        """
        Trigger: User has sent ≥ N messages without mentioning a budget.
        Prompts them to set one so recommendations can be filtered.
        """
        if context.budget_usd is not None:
            return None  # Budget already known
        if user_message_count < _BUDGET_PROMPT_AFTER:
            return None  # Too early to ask

        return Suggestion(
            name="💰 Set Your Budget",
            activity_type="educational",
            description=(
                "Setting a budget helps me give you much more accurate recommendations. "
                "You can say something like 'My budget is $1,000' or 'I'm travelling on a tight budget.'"
            ),
            is_proactive=True,
            tags=["prompt", "budget"],
        )

    def _check_no_destination(
        self, context: TravelContext, user_message_count: int
    ) -> Optional[Suggestion]:
        """
        Trigger: User has sent ≥ N messages without naming a destination.
        """
        if context.destination:
            return None
        if user_message_count < _DESTINATION_PROMPT_AFTER:
            return None

        return Suggestion(
            name="📍 Where Are You Headed?",
            activity_type="sightseeing",
            description=(
                "I'd love to help you more precisely! "
                "Which destination are you thinking about? "
                "Even a broad region (e.g., 'Southeast Asia', 'Europe') helps."
            ),
            is_proactive=True,
            tags=["prompt", "destination"],
        )

    def _check_long_trip(self, context: TravelContext) -> Optional[Suggestion]:
        """
        Trigger: Trip duration > 14 days → suggest multi-city planning.
        """
        if context.duration_days is None or context.duration_days <= 14:
            return None

        return Suggestion(
            name="🗺️ Multi-City Itinerary",
            activity_type="sightseeing",
            description=(
                f"With {context.duration_days} days, you have time to explore multiple cities. "
                "Would you like me to help you structure a multi-destination itinerary?"
            ),
            is_proactive=True,
            tags=["itinerary", "multi-city"],
        )

    def _check_solo_social(self, context: TravelContext) -> Optional[Suggestion]:
        """
        Trigger: Solo traveller hasn't mentioned social activities.
        Suggest social experiences.
        """
        is_solo = context.group_size == 1 or context.travel_style == "solo"
        has_social = "social" in context.activity_types or "social" in context.interests

        if not is_solo or has_social:
            return None

        return Suggestion(
            name="👥 Meet Fellow Travellers",
            activity_type="social",
            description=(
                "As a solo traveller, joining group tours or meetups is a great way "
                "to meet people and enhance your experience. "
                "Many hostels and travel platforms organise social events."
            ),
            is_proactive=True,
            tags=["solo", "social", "recommended"],
        )

    def _check_family_friendly(self, context: TravelContext) -> Optional[Suggestion]:
        """
        Trigger: Family group (4+ people) → highlight kid-friendly activities.
        """
        is_family = (
            context.travel_style == "family"
            or (context.group_size is not None and context.group_size >= 4)
        )
        already_suggested = "family" in context.interests

        if not is_family or already_suggested:
            return None

        destination_hint = f" in {context.destination}" if context.destination else ""
        return Suggestion(
            name="👨‍👩‍👧‍👦 Kid-Friendly Activities",
            activity_type="educational",
            description=(
                f"Travelling with family? Look for interactive museums, theme parks, "
                f"and nature reserves{destination_hint} — they're engaging for all ages. "
                "Always check age recommendations and opening times in advance."
            ),
            is_proactive=True,
            tags=["family", "kids", "educational"],
        )
