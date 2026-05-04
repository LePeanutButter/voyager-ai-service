"""
Context extractor — rule-based intent and entity extraction.

Analyses raw user messages to extract:
  - Intent        : What the user is trying to accomplish
  - TravelContext : Structured domain entities (destination, budget, etc.)

Design:
  - Pure functions / stateless class; all inputs come from the caller
  - Uses regex + keyword dictionaries — no ML dependencies
  - Aligned with backend domain: ActivityType (13 values), TravelType (10 values)
  - Defensive: returns partial context gracefully on any extraction failure
  - Extendable: swap _extract_destination() for an NER model without changing
    the public interface
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

from app.chat.schemas import ChatIntent, TravelContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyword dictionaries (aligned with backend enums)
# ---------------------------------------------------------------------------

# Maps destination keywords to canonical destination names
_DESTINATION_PATTERNS = [
    # Pattern: "to/in/visit/going to/travel to <City>"
    r"(?:to|in|visit(?:ing)?|going to|travel(?:ling)? to|fly(?:ing)? to|head(?:ing)? to)\s+([A-Z][a-zA-Z\s]{2,30}?)(?:\s|,|\.|$)",
    # Pattern: "<City> trip/vacation/holiday"
    r"([A-Z][a-zA-Z\s]{2,20}?)\s+(?:trip|vacation|holiday|getaway|tour|journey)",
    # Pattern: "plan.*<City>"
    r"plan\w*\s+(?:a\s+)?(?:trip\s+(?:to\s+)?)?([A-Z][a-zA-Z\s]{2,20}?)(?:\s|,|\.|$)",
]

# Budget extraction patterns → (regex, multiplier)
_BUDGET_PATTERNS: List[Tuple[str, float]] = [
    # "$1,500" or "1500 dollars"
    (r"\$\s*([\d,]+(?:\.\d{1,2})?)\s*(?:USD|dollars?|usd)?", 1.0),
    (r"([\d,]+(?:\.\d{1,2})?)\s*(?:USD|dollars?|usd)", 1.0),
    # "1.5k" → 1500
    (r"\$?\s*([\d.]+)\s*k\b", 1000.0),
    # "budget of 500"
    (r"budget\s+(?:of\s+|around\s+|about\s+)?\$?\s*([\d,]+)", 1.0),
    # "around/about/roughly $500"
    (r"(?:around|about|roughly|approximately)\s+\$?\s*([\d,]+)", 1.0),
]

# Duration extraction patterns → (regex, days_multiplier)
# NOTE: _extract_duration_patterns() expects match.group(1) to be a numeric
# string and converts it with int(). Keep only patterns that satisfy that
# contract here. Non-numeric phrases (e.g. "a week", "a couple of days") are
# handled separately by _extract_duration_special().
_DURATION_PATTERNS: List[Tuple[str, int]] = [
    (r"(\d+)\s*-?\s*(?:days?|nights?)", 1),
    (r"(\d+)\s*-?\s*(?:weeks?)", 7),
]

# Group size patterns
_GROUP_PATTERNS: List[Tuple[str, int]] = [
    (r"(\d+)\s+(?:people|persons?|travelers?|travellers?|adults?|guests?|of us)", 0),
    (r"solo|alone|by myself|on my own", 1),
    (r"couple|partner|spouse|wife|husband|girlfriend|boyfriend", 2),
    (r"family", 4),
    (r"group of (\d+)", 0),
]

# Travel style keyword → TravelType mapping
_STYLE_KEYWORDS: Dict[str, str] = {
    "adventure": "adventure", "hiking": "adventure", "trekking": "adventure",
    "backpacking": "adventure", "extreme": "adventure",
    "cultural": "cultural", "museum": "cultural", "history": "cultural",
    "heritage": "cultural", "architecture": "cultural",
    "relaxation": "leisure", "relax": "leisure", "leisure": "leisure",
    "chill": "leisure", "unwind": "leisure", "spa": "leisure",
    "romantic": "romantic", "honeymoon": "romantic", "anniversary": "romantic",
    "couple": "romantic",
    "family": "family", "kids": "family", "children": "family",
    "child-friendly": "family",
    "solo": "solo", "alone": "solo", "by myself": "solo",
    "business": "business", "conference": "business", "work trip": "business",
    "luxury": "leisure", "premium": "leisure",
    "budget": "leisure", "cheap": "leisure", "affordable": "leisure",
}

# Activity interest keywords → ActivityType mapping
_INTEREST_KEYWORDS: Dict[str, str] = {
    "food": "dining", "eat": "dining", "restaurant": "dining",
    "cuisine": "dining", "dining": "dining", "gastronomy": "dining",
    "museum": "cultural", "art": "cultural", "culture": "cultural",
    "gallery": "cultural", "history": "cultural",
    "hiking": "adventure", "trekking": "adventure", "climb": "adventure",
    "adventure": "adventure", "kayak": "adventure", "surf": "adventure",
    "dive": "adventure", "snorkel": "adventure",
    "beach": "relaxation", "spa": "relaxation", "relax": "relaxation",
    "yoga": "relaxation", "meditation": "relaxation", "wellness": "relaxation",
    "shopping": "shopping", "market": "shopping", "bazaar": "shopping",
    "mall": "shopping",
    "nightlife": "entertainment", "club": "entertainment", "bar": "entertainment",
    "concert": "entertainment", "show": "entertainment",
    "sport": "sports", "football": "sports", "tennis": "sports",
    "golf": "sports", "cycling": "sports", "bike": "sports",
    "photography": "sightseeing", "sightseeing": "sightseeing",
    "tour": "sightseeing", "landmark": "sightseeing",
    "education": "educational", "learn": "educational", "workshop": "educational",
    "mountain": "adventure", "valley": "adventure", "forest": "adventure",
    "nature": "adventure", "wildlife": "adventure", "safari": "adventure",
}

# Greeting patterns
_GREETING_PATTERNS = re.compile(
    r"^(?:hi|hello|hey|hola|good\s+(?:morning|afternoon|evening)|greetings?|howdy|sup|what'?s\s+up)\b",
    re.IGNORECASE,
)

# Budget-related question patterns
_BUDGET_QUESTION_PATTERNS = re.compile(
    r"(?:how\s+much|what\s+(?:does|would|will|is)|cost|price|fee|expense|afford|budget)",
    re.IGNORECASE,
)


class ContextExtractor:
    """
    Stateless rule-based extractor for chat messages.

    All methods are synchronous — call them from async code freely.
    """

    def extract(self, message: str) -> Tuple[ChatIntent, TravelContext]:
        """
        Main extraction entry point.

        Args:
            message: Raw user message string.

        Returns:
            (intent, partial_context) — partial_context only contains
            fields that were actually found; missing fields remain None.
        """
        if not message or not message.strip():
            return ChatIntent.UNKNOWN, TravelContext()

        try:
            context = self._extract_context(message)
            intent = self._classify_intent(message, context)
            return intent, context
        except Exception as exc:
            logger.warning("Context extraction error (non-fatal): %s", exc, exc_info=True)
            return ChatIntent.UNKNOWN, TravelContext()

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def _classify_intent(
        self, message: str, context: Optional["TravelContext"] = None
    ) -> ChatIntent:
        msg = message.strip().lower()

        if _GREETING_PATTERNS.match(msg):
            return ChatIntent.GREETING

        # Budget-specific question
        if _BUDGET_QUESTION_PATTERNS.search(msg) and not self._has_destination_hint(msg):
            return ChatIntent.BUDGET_QUESTION

        # Explicit planning intent
        planning_kws = r"\b(?:plan|trip|travel|visit|go to|fly to|vacation|holiday|itinerary|journey|tour)\b"
        if re.search(planning_kws, msg):
            return ChatIntent.TRAVEL_PLANNING

        # Activity-specific query
        activity_kws = r"\b(?:activities|things to do|what to do|see|experience|recommend|suggestion|suggest)\b"
        if re.search(activity_kws, msg):
            return ChatIntent.ACTIVITY_QUERY

        # Destination question
        dest_kws = r"\b(?:where|destination|place|country|city)\b"
        if re.search(dest_kws, msg):
            return ChatIntent.DESTINATION_QUERY

        # If we extracted context fields, it's likely a travel planning message
        ctx = context if context is not None else self._extract_context(message)
        if ctx.destination or ctx.budget_usd or ctx.duration_days:
            return ChatIntent.TRAVEL_PLANNING

        return ChatIntent.FOLLOW_UP

    def _has_destination_hint(self, msg: str) -> bool:
        """Check if the message contains any destination-like pattern."""
        for pattern in _DESTINATION_PATTERNS:
            if re.search(pattern, msg, re.IGNORECASE):
                return True
        return False

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    def _extract_context(self, message: str) -> TravelContext:
        """Extract all domain entities from a message."""
        return TravelContext(
            destination=self._extract_destination(message),
            budget_usd=self._extract_budget(message),
            duration_days=self._extract_duration(message),
            group_size=self._extract_group_size(message),
            travel_style=self._extract_travel_style(message),
            interests=self._extract_interests(message),
            activity_types=self._extract_activity_types(message),
            keyword_counts=self._count_keywords(message),
        )

    def _extract_destination_known(self, msg_lower: str) -> Optional[str]:
        known_places = [
            "Cancun", "Tulum", "Bali", "Phuket", "Rome", "Kyoto", 
            "Cairo", "Istanbul", "Paris", "Venice", "Santorini", "Prague",
            "Mexico", "Italy", "France", "Indonesia", "Thailand", 
            "Japan", "Egypt", "Turkey", "Greece", "Czech Republic"
        ]
        for place in known_places:
            if re.search(r"\b" + re.escape(place.lower()) + r"\b", msg_lower):
                return place
        return None

    def _extract_destination_regex(self, message: str) -> Optional[str]:
        invalid_words = {
            "the", "this", "that", "my", "our", "your", "some", "any",
            "few", "all", "more", "less", "beach", "cheap", "romantic",
            "travel", "trip", "day", "days", "vacation", "holiday", 
            "want", "need", "like", "love", "go", "going", "visit", 
            "relax", "relaxed", "relaxing", "cultural", "adventure"
        }
        for pattern in _DESTINATION_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
            if match:
                destination = match.group(1).strip().title()
                dest_lower = destination.lower()
                words = dest_lower.split()
                if len(destination) >= 3 and not any(w in invalid_words for w in words):
                    return destination
        return None

    def _extract_destination(self, message: str) -> Optional[str]:
        """Extract a destination place name from the message."""
        known = self._extract_destination_known(message.lower())
        if known:
            return known
            
        return self._extract_destination_regex(message)

    def _extract_budget_patterns(self, message: str) -> Optional[float]:
        for pattern, multiplier in _BUDGET_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(",", "")
                try:
                    value = float(raw) * multiplier
                    if 1 <= value <= 1_000_000:
                        return round(value, 2)
                except ValueError:
                    continue
        return None

    def _extract_budget_qualitative(self, msg_lower: str) -> Optional[float]:
        if re.search(r"\bvery\s+cheap\b|\bshoestring\b|\bextremely\s+budget\b", msg_lower):
            return 200.0
        if re.search(r"\bcheap\b|\blow\s+budget\b|\bbackpack\b|\bbudget\s+travel\b", msg_lower):
            return 400.0
        if re.search(r"\bmid[\s-]?range\b|\bmoderate\b|\bcomfort\w*\b", msg_lower):
            return 1000.0
        if re.search(r"\bluxury\b|\bpremium\b|\bfive[\s-]?star\b|\bupscale\b", msg_lower):
            return 5000.0
        return None

    def _extract_budget(self, message: str) -> Optional[float]:
        """Extract a numeric budget value (USD) from the message."""
        if re.search(r"no\s+budget|unlimited|any\s+budget|don'?t\s+(?:care|mind)", message, re.I):
            return None

        val = self._extract_budget_patterns(message)
        if val is not None:
            return val

        return self._extract_budget_qualitative(message.lower())

    def _extract_duration_special(self, msg_lower: str) -> Optional[int]:
        if re.search(r"\ba\s+week\b|\bone\s+week\b", msg_lower):
            return 7
        if re.search(r"\btwo\s+weeks?\b", msg_lower):
            return 14
        if re.search(r"\bthree\s+weeks?\b", msg_lower):
            return 21
        if re.search(r"\b(?:a\s+)?(?:long\s+)?weekend\b", msg_lower):
            return 3
        if re.search(r"\ba\s+month\b|\bone\s+month\b", msg_lower):
            return 30
        return None

    def _extract_duration_patterns(self, message: str) -> Optional[int]:
        for pattern, multiplier in _DURATION_PATTERNS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                try:
                    raw = int(match.group(1))
                    total = raw * multiplier
                    if 1 <= total <= 365:
                        return total
                except (ValueError, IndexError):
                    continue
        return None

    def _extract_duration(self, message: str) -> Optional[int]:
        """Extract trip duration in days from the message."""
        msg_lower = message.lower()
        special_dur = self._extract_duration_special(msg_lower)
        if special_dur is not None:
            return special_dur
            
        return self._extract_duration_patterns(message)

    def _extract_group_size_qualitative(self, msg_lower: str) -> Optional[int]:
        if re.search(r"\bsolo\b|\balone\b|\bby myself\b|\bon my own\b", msg_lower):
            return 1
        if re.search(r"\bcouple\b|\bpartner\b|\bspouse\b|\bwife\b|\bhusband\b|\bgirlfriend\b|\bboyfriend\b", msg_lower):
            return 2
        if re.search(r"\bfamily\b", msg_lower):
            return 4  # conservative default
        return None

    def _extract_group_size_patterns(self, msg_lower: str) -> Optional[int]:
        for pattern, fixed in _GROUP_PATTERNS:
            if fixed > 0:
                if re.search(pattern, msg_lower):
                    return fixed
            elif fixed == 0:
                match = re.search(pattern, msg_lower)
                if match:
                    try:
                        val = int(match.group(1))
                        if 1 <= val <= 50:
                            return val
                    except (ValueError, IndexError):
                        continue
        return None

    def _extract_group_size(self, message: str) -> Optional[int]:
        """Extract the number of travelers from the message."""
        msg_lower = message.lower()
        
        qualitative = self._extract_group_size_qualitative(msg_lower)
        if qualitative is not None:
            return qualitative
            
        return self._extract_group_size_patterns(msg_lower)

    def _extract_travel_style(self, message: str) -> Optional[str]:
        """Extract travel style from the message (maps to TravelType)."""
        msg_lower = message.lower()
        for keyword, style in _STYLE_KEYWORDS.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower):
                return style
        return None

    def _extract_interests(self, message: str) -> List[str]:
        """Extract free-form interest tags from the message."""
        msg_lower = message.lower()
        found: List[str] = []
        for keyword in _INTEREST_KEYWORDS:
            if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower) and keyword not in found:
                found.append(keyword)
        return found

    def _extract_activity_types(self, message: str) -> List[str]:
        """Extract ActivityType values mentioned in the message."""
        msg_lower = message.lower()
        found: List[str] = []
        seen: set = set()
        for keyword, activity_type in _INTEREST_KEYWORDS.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", msg_lower) and activity_type not in seen:
                found.append(activity_type)
                seen.add(activity_type)
        return found

    def _count_keywords(self, message: str) -> Dict[str, int]:
        """
        Count occurrences of interest keywords in the message.
        Used by the ProactiveEngine to detect repeated topics.
        """
        msg_lower = message.lower()
        counts: Dict[str, int] = {}
        for keyword in _INTEREST_KEYWORDS:
            occurrences = len(re.findall(r"\b" + re.escape(keyword) + r"\b", msg_lower))
            if occurrences > 0:
                counts[keyword] = occurrences
        return counts
