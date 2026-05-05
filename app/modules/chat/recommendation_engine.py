"""
Chat Recommendation Engine.

Provides context-aware, highly specific travel recommendations using an
internal curated dataset of destinations and activities.

Logic:
  - If destination is missing: Suggests destinations based on tags (e.g. beach, budget).
  - If destination is specified: Suggests concrete activities (e.g. "Visit Colosseum").
  - Budget: Filters or prioritizes free/cheap activities if budget is low.
  - Duration: Distributes activities by day (approx 2 per day) if specified.
"""

import logging
from typing import Dict, List, Optional, Tuple

from app.modules.chat.schemas import Suggestion, TravelContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Curated Dataset
# ---------------------------------------------------------------------------

_DESTINATIONS = {
    "Cancun": {"country": "Mexico", "tags": ["beach", "leisure", "relaxation", "mid-range"]},
    "Tulum": {"country": "Mexico", "tags": ["beach", "romantic", "premium", "nature"]},
    "Bali": {"country": "Indonesia", "tags": ["beach", "romantic", "budget", "adventure"]},
    "Phuket": {"country": "Thailand", "tags": ["beach", "leisure", "budget", "entertainment"]},
    "Rome": {"country": "Italy", "tags": ["cultural", "sightseeing", "mid-range", "food"]},
    "Kyoto": {"country": "Japan", "tags": ["cultural", "romantic", "premium", "relaxation"]},
    "Cairo": {"country": "Egypt", "tags": ["cultural", "adventure", "budget", "history"]},
    "Istanbul": {"country": "Turkey", "tags": ["cultural", "shopping", "mid-range", "food"]},
    "Paris": {"country": "France", "tags": ["romantic", "cultural", "premium", "food"]},
    "Venice": {"country": "Italy", "tags": ["romantic", "cultural", "premium", "sightseeing"]},
    "Santorini": {"country": "Greece", "tags": ["romantic", "beach", "premium", "relaxation"]},
    "Prague": {"country": "Czech Republic", "tags": ["romantic", "cultural", "budget", "sightseeing"]}
}

_COUNTRY_MAP = {
    "Mexico": ["Cancun", "Tulum"],
    "Italy": ["Rome", "Venice"],
    "France": ["Paris"],
    "Indonesia": ["Bali"],
    "Thailand": ["Phuket"],
    "Japan": ["Kyoto"],
    "Egypt": ["Cairo"],
    "Turkey": ["Istanbul"],
    "Greece": ["Santorini"],
    "Czech Republic": ["Prague"]
}

_ACTIVITIES = {
    "Cancun": [
        {"name": "Relax at Playa Delfines", "type": "relaxation", "cost": 0, "tags": ["beach", "free"]},
        {"name": "Explore Chichen Itza", "type": "cultural", "cost": 60, "tags": ["educational"]},
        {"name": "Snorkel at Isla Mujeres", "type": "adventure", "cost": 45, "tags": ["active", "beach"]},
        {"name": "Dine at La Isla Village", "type": "dining", "cost": 30, "tags": ["food", "leisure"]},
    ],
    "Tulum": [
        {"name": "Relax at Playa Paraiso", "type": "relaxation", "cost": 0, "tags": ["beach", "romantic", "free"]},
        {"name": "Visit Tulum Mayan Ruins", "type": "cultural", "cost": 10, "tags": ["sightseeing", "budget"]},
        {"name": "Swim in Gran Cenote", "type": "adventure", "cost": 25, "tags": ["nature", "budget"]},
        {"name": "Romantic Dinner at Hartwood", "type": "dining", "cost": 100, "tags": ["romantic", "premium"]},
    ],
    "Bali": [
        {"name": "Watch sunset at Uluwatu Temple", "type": "cultural", "cost": 5, "tags": ["romantic", "budget"]},
        {"name": "Surf at Kuta Beach", "type": "sports", "cost": 15, "tags": ["beach", "active", "budget"]},
        {"name": "Trek Mount Batur at sunrise", "type": "adventure", "cost": 40, "tags": ["nature"]},
        {"name": "Couples Spa Treatment in Ubud", "type": "relaxation", "cost": 30, "tags": ["romantic"]},
    ],
    "Phuket": [
        {"name": "Relax at Patong Beach", "type": "relaxation", "cost": 0, "tags": ["beach", "free"]},
        {"name": "Boat tour to Phi Phi Islands", "type": "adventure", "cost": 50, "tags": ["nature"]},
        {"name": "Visit the Big Buddha", "type": "cultural", "cost": 0, "tags": ["sightseeing", "free"]},
        {"name": "Explore Bangla Road Nightlife", "type": "entertainment", "cost": 20, "tags": ["social", "budget"]},
    ],
    "Rome": [
        {"name": "Visit the Colosseum and Roman Forum", "type": "cultural", "cost": 20, "tags": ["sightseeing"]},
        {"name": "Walk through Trastevere at night", "type": "social", "cost": 0, "tags": ["romantic", "free"]},
        {"name": "Tour the Vatican Museums", "type": "cultural", "cost": 30, "tags": ["educational"]},
        {"name": "Authentic Pasta Dinner near Piazza Navona", "type": "dining", "cost": 25, "tags": ["food", "budget"]},
    ],
    "Kyoto": [
        {"name": "Walk through Fushimi Inari Shrine", "type": "cultural", "cost": 0, "tags": ["sightseeing", "free", "romantic"]},
        {"name": "Traditional Tea Ceremony", "type": "educational", "cost": 40, "tags": ["cultural", "romantic"]},
        {"name": "Explore Arashiyama Bamboo Grove", "type": "relaxation", "cost": 0, "tags": ["nature", "free"]},
        {"name": "Kaiseki Dinner Experience", "type": "dining", "cost": 150, "tags": ["food", "premium", "romantic"]},
    ],
    "Cairo": [
        {"name": "Visit the Pyramids of Giza", "type": "sightseeing", "cost": 15, "tags": ["cultural", "educational", "budget"]},
        {"name": "Explore the Egyptian Museum", "type": "cultural", "cost": 10, "tags": ["history", "budget"]},
        {"name": "Shop at Khan el-Khalili Bazaar", "type": "shopping", "cost": 5, "tags": ["social", "budget"]},
        {"name": "Felucca Ride on the Nile at sunset", "type": "relaxation", "cost": 15, "tags": ["romantic", "budget"]},
    ],
    "Istanbul": [
        {"name": "Tour the Hagia Sophia", "type": "cultural", "cost": 0, "tags": ["sightseeing", "free"]},
        {"name": "Shop at the Grand Bazaar", "type": "shopping", "cost": 0, "tags": ["social", "free"]},
        {"name": "Bosphorus Sunset Cruise", "type": "entertainment", "cost": 25, "tags": ["romantic", "budget"]},
        {"name": "Traditional Turkish Bath (Hammam)", "type": "relaxation", "cost": 50, "tags": ["cultural"]},
    ],
    "Paris": [
        {"name": "Eiffel Tower Sunset Viewing", "type": "sightseeing", "cost": 30, "tags": ["romantic", "premium"]},
        {"name": "Explore the Louvre Museum", "type": "cultural", "cost": 20, "tags": ["educational"]},
        {"name": "Romantic Seine River Cruise", "type": "entertainment", "cost": 25, "tags": ["romantic"]},
        {"name": "Stroll and Cafe in Montmartre", "type": "leisure", "cost": 10, "tags": ["budget", "relaxation", "romantic"]},
    ],
    "Venice": [
        {"name": "Private Gondola Ride", "type": "entertainment", "cost": 90, "tags": ["romantic", "premium"]},
        {"name": "Visit St. Mark's Basilica", "type": "cultural", "cost": 0, "tags": ["sightseeing", "free"]},
        {"name": "Explore the Doge's Palace", "type": "cultural", "cost": 30, "tags": ["educational"]},
        {"name": "Cicchetti and Wine Tasting", "type": "dining", "cost": 25, "tags": ["food", "budget", "romantic"]},
    ],
    "Santorini": [
        {"name": "Watch the sunset in Oia", "type": "relaxation", "cost": 0, "tags": ["romantic", "free"]},
        {"name": "Catamaran Cruise in the Caldera", "type": "adventure", "cost": 120, "tags": ["premium", "nature"]},
        {"name": "Wine Tasting at a Local Vineyard", "type": "dining", "cost": 40, "tags": ["romantic"]},
        {"name": "Relax at the Red Beach", "type": "relaxation", "cost": 0, "tags": ["beach", "free"]},
    ],
    "Prague": [
        {"name": "Walk across the Charles Bridge at dawn", "type": "sightseeing", "cost": 0, "tags": ["romantic", "free"]},
        {"name": "Explore Prague Castle", "type": "cultural", "cost": 15, "tags": ["educational", "budget"]},
        {"name": "Drink Local Pilsner in Old Town", "type": "dining", "cost": 10, "tags": ["budget", "social"]},
        {"name": "Vltava River Jazz Cruise", "type": "entertainment", "cost": 35, "tags": ["romantic"]},
    ]
}


def _budget_tier(budget_usd: Optional[float]) -> str:
    if budget_usd is None:
        return "mid-range"
    if budget_usd < 500:
        return "budget"
    if budget_usd < 2000:
        return "mid-range"
    return "premium"


class ChatRecommendationEngine:
    """Generates context-aware, specific suggestions."""

    def _resolve_destination(self, context: TravelContext, user_tags: set, tier: str) -> Tuple[str, str]:
        chosen_dest = context.destination.title() if context.destination else None
        reasoning_str = ""
        
        if not chosen_dest or chosen_dest in _COUNTRY_MAP:
            scored = []
            cities_to_score = _COUNTRY_MAP[chosen_dest] if chosen_dest in _COUNTRY_MAP else _DESTINATIONS.keys()
            for dest in cities_to_score:
                info = _DESTINATIONS[dest]
                score = 0
                dest_tags = info["tags"]
                if tier in dest_tags: score += 2
                for tag in user_tags:
                    if tag in dest_tags: score += 3
                scored.append((score, dest, info))
                
            scored.sort(key=lambda x: x[0], reverse=True)
            top_dest = scored[0][1]
            top_info = scored[0][2]
            
            if context.destination and context.destination.title() in _COUNTRY_MAP:
                reasoning_str = f"Selected {top_dest} as the best match for your trip to {context.destination.title()}."
            else:
                match_tags = [t for t in user_tags if t in top_info["tags"]]
                if match_tags:
                    reason_tags = " and ".join(match_tags[:2])
                    reasoning_str = f"Selected because it perfectly matches your preference for {reason_tags}."
                else:
                    reasoning_str = f"Selected because it fits your {tier} budget profile perfectly."
            
            chosen_dest = top_dest
        else:
            reasoning_str = f"Focused on {chosen_dest} to match your request."
            
        return chosen_dest, reasoning_str

    def _build_itinerary_for_destination(
        self, 
        dest_query: str, 
        reasoning_str: str, 
        context: TravelContext, 
        user_tags: set, 
        tier: str, 
        max_suggestions: int
    ) -> List[Suggestion]:
        is_low_budget = context.budget_usd is not None and context.budget_usd < 500
        suggestions = []

        country = _DESTINATIONS.get(dest_query, {}).get("country", "")
        dest_display = f"{dest_query}, {country}" if country and country not in dest_query else dest_query
        
        suggestions.append(Suggestion(
            name=dest_display,
            activity_type="destination",
            description=reasoning_str,
            budget_tier=tier,
            tags=[]
        ))

        raw_activities = []
        if dest_query in _ACTIVITIES:
            for act in _ACTIVITIES[dest_query]:
                act["city"] = dest_query
                raw_activities.append(act)
        
        if not raw_activities:
            raw_activities = [
                {"name": "Explore the city center", "type": "sightseeing", "cost": 0, "tags": ["free", "sightseeing"], "city": dest_query},
                {"name": "Dine at a local restaurant", "type": "dining", "cost": 30, "tags": ["food", "local"], "city": dest_query},
                {"name": "Visit the main cultural district", "type": "cultural", "cost": 15, "tags": ["educational", "cultural"], "city": dest_query},
                {"name": "Relax in prominent parks", "type": "relaxation", "cost": 0, "tags": ["free", "nature"], "city": dest_query},
            ]

        filtered = []
        for act in raw_activities:
            if is_low_budget:
                if act["cost"] > 40 or "premium" in act["tags"]:
                    continue
            filtered.append(act)

        def score_act(act):
            score = 0
            if is_low_budget and ("free" in act["tags"] or "budget" in act["tags"] or act["cost"] == 0):
                score += 10
            for tag in user_tags:
                if tag in act["tags"] or tag == act["type"]:
                    score += 5
            return score

        filtered.sort(key=score_act, reverse=True)

        if context.duration_days and context.duration_days > 0:
            day = 1
            count = 0
            acts_per_day = 2
            
            for act in filtered:
                sugg_name = f"Day {day}: {act['name']}"
                
                suggestions.append(Suggestion(
                    name=sugg_name,
                    activity_type=act["type"],
                    description="",
                    estimated_cost_usd=float(act["cost"]) if act["cost"] > 0 else 0.0,
                    budget_tier=tier,
                    tags=act["tags"]
                ))
                
                count += 1
                if count >= acts_per_day:
                    day += 1
                    count = 0
                    if day > context.duration_days:
                        break
        else:
            for act in filtered[:max_suggestions]:
                suggestions.append(Suggestion(
                    name=act['name'],
                    activity_type=act["type"],
                    description="",
                    estimated_cost_usd=float(act["cost"]) if act["cost"] > 0 else 0.0,
                    budget_tier=tier,
                    tags=act["tags"]
                ))

        return suggestions

    def generate(
        self,
        context: TravelContext,
        max_suggestions: int = 5,
    ) -> List[Suggestion]:
        if max_suggestions <= 0:
            return []

        user_tags = set(context.interests + context.activity_types)
        if context.travel_style:
            user_tags.add(context.travel_style)
            
        tier = _budget_tier(context.budget_usd)

        chosen_dest, reasoning_str = self._resolve_destination(context, user_tags, tier)
        return self._build_itinerary_for_destination(chosen_dest, reasoning_str, context, user_tags, tier, max_suggestions)

    def generate_for_activity_types(
        self,
        context: TravelContext,
        max_suggestions: int = 5,
    ) -> List[Suggestion]:
        return self.generate(context, max_suggestions)
