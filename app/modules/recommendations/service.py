"""Personalized travel recommendations, destinations, and contextual activities.

Purpose:
    Score mock activity catalogs, diversify ranked lists, cache responses,
    and blend trend signals for destination cards (Feature 15 / PBI 24–30).

Responsibilities:
    Activity generation, similarity search, feedback hooks, destination catalog
    ranking, and GPS/weather-aware contextual pools.

Dependencies:
    ``settings``, enums and base schemas, ``recommendations.schemas``,
    ``model_manager``, optional ``TrendsService``.
"""

from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.seasonality.service import SeasonalityService
    from app.modules.trends.service import TrendsService
import logging
import math
import random
import secrets
from datetime import datetime, timedelta, timezone

from app.modules.common.schemas.enums import ActivityType, TravelPreference, WeatherCondition
from app.modules.common.schemas.base import Location
from app.modules.recommendations.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    Activity,
    DestinationCard,
    DestinationRecommendationRequest,
    DestinationRecommendationResponse,
    ContextualActivityRequest,
    ContextualActivityResponse,
)
from app.core.config import settings

logger = logging.getLogger(__name__)
_SAFE_RANDOM = secrets.SystemRandom()

# Curated catalog for PBI 24 (destinations). Tags align with TravelPreference themes.
_DESTINATION_CATALOG: List[Dict[str, Any]] = [
    {"destination_id": "dst_barcelona", "name": "Barcelona", "country": "Spain", "tags": ["cultural", "foodie", "beach"]},
    {"destination_id": "dst_kyoto", "name": "Kyoto", "country": "Japan", "tags": ["cultural", "relaxation"]},
    {"destination_id": "dst_queenstown", "name": "Queenstown", "country": "New Zealand", "tags": ["adventure", "nature"]},
    {"destination_id": "dst_maldives", "name": "Maldives", "country": "Maldives", "tags": ["beach", "relaxation", "luxury"]},
    {"destination_id": "dst_lima", "name": "Lima", "country": "Peru", "tags": ["cultural", "foodie"]},
    {"destination_id": "dst_reykjavik", "name": "Reykjavik", "country": "Iceland", "tags": ["adventure", "nature"]},
    {"destination_id": "dst_marrakech", "name": "Marrakech", "country": "Morocco", "tags": ["cultural", "foodie", "adventure"]},
    {"destination_id": "dst_bali", "name": "Bali", "country": "Indonesia", "tags": ["beach", "relaxation", "nature"]},
    {"destination_id": "dst_lisbon", "name": "Lisbon", "country": "Portugal", "tags": ["cultural", "foodie", "beach"]},
    {"destination_id": "dst_patagonia", "name": "Patagonia", "country": "Argentina/Chile", "tags": ["adventure", "nature"]},
    # Feature 15 (PBI 30) — también en señales de tendencias / dashboard
    {"destination_id": "dst_azores", "name": "Azores", "country": "Portugal", "tags": ["nature", "adventure", "relaxation"]},
    {"destination_id": "dst_georgia", "name": "Georgia (Caucasus)", "country": "Georgia", "tags": ["cultural", "foodie", "adventure"]},
    {"destination_id": "dst_slovenia", "name": "Slovenia", "country": "Slovenia", "tags": ["nature", "cultural", "foodie"]},
]


class RecommendationService:
    """Facade over mock data sources with scoring, diversity, and caching.

    Attributes:
        model_manager: Registry for optional recommendation models.
        trends_service: Optional trends feed for emerging destinations.
        cache: In-memory map of hashed recommendation responses.
    """

    def __init__(
        self,
        model_manager,
        trends_service: Optional["TrendsService"] = None,
        seasonality_service: Optional["SeasonalityService"] = None,
    ):
        """Attaches models and optional trends / seasonality collaborators.

        Args:
            model_manager: Shared ``ModelManager``.
            trends_service: Used when ``include_emerging_trends`` is requested.
            seasonality_service: Mitigación estacional en ranking de destinos (paper).
        """
        self.model_manager = model_manager
        self.trends_service = trends_service
        self.seasonality_service = seasonality_service
        self.cache = {}  # Simple in-memory cache (replace with Redis in production)
    
    def generate_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        """Scores candidates, diversifies, explains, caches, and returns confidences.

        Args:
            request: User id, location, filters, preferences, and ``max_results``.

        Returns:
            ``RecommendationResponse`` with ranked ``Activity`` rows and explanations.

        Raises:
            Exception: Logged and re-raised on pipeline failures.
        """
        try:
            logger.info(f"Generating recommendations for user {request.user_id}")
            
            # Get user profile for personalization
            user_profile = self._get_user_profile(request.user_id)
            
            # Get candidate activities based on location and filters
            candidate_activities = self._get_candidate_activities(request)
            
            # Score activities using ML models and business rules
            scored_activities = self._score_activities(
                candidate_activities, 
                user_profile, 
                request
            )
            
            # Apply diversity and ranking algorithms
            final_recommendations = self._apply_ranking_and_diversity(
                scored_activities, 
                request.max_results
            )
            
            # Generate explanation for recommendations
            explanation = self._generate_explanation(
                final_recommendations, 
                user_profile
            )
            
            confidence_scores = []
            for act in final_recommendations:
                data = act.model_dump()
                confidence_scores.append(float(data.get("confidence_score") or 0.0))

            response = RecommendationResponse(
                recommendations=final_recommendations,
                user_id=request.user_id,
                generated_at=datetime.now(timezone.utc),
                total_results=len(final_recommendations),
                confidence_scores=confidence_scores,
                explanation=explanation
            )
            
            # Cache the response for future requests
            cache_key = f"rec_{request.user_id}_{hash(str(request.location))}"
            self.cache[cache_key] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            raise
    
    def get_popular_activities(self, location: str, limit: int) -> List[Activity]:
        """Returns mock activities for ``location`` sorted by rating (with jitter).

        Args:
            location: City/region label for mock generation.
            limit: Cap on returned items.

        Returns:
            Top ``limit`` activities by rating.

        Raises:
            Exception: Logged and re-raised if mock generation fails.
        """
        try:
            # Mock implementation - in production, query database
            mock_activities = self._generate_mock_activities(location, limit)
            
            # Sort by rating and popularity
            popular_activities = sorted(
                mock_activities, 
                key=lambda x: (x.rating, _SAFE_RANDOM.random()), 
                reverse=True
            )[:limit]
            
            return popular_activities
            
        except Exception as e:
            logger.error(f"Error fetching popular activities: {str(e)}")
            raise
    
    def get_trending_activities(self, category: Optional[str], limit: int) -> List[Activity]:
        """Simulates trending via boosted mock scores and optional category filter.

        Args:
            category: When set, filters by ``ActivityType`` string match.
            limit: Number of trending rows to return.

        Returns:
            Trending-scored activities capped at ``limit``.

        Raises:
            Exception: Logged and re-raised on generation errors.
        """
        try:
            # Mock implementation - in production, analyze recent interactions
            mock_activities = self._generate_mock_activities("global", limit * 2)
            
            # Filter by category if specified
            if category:
                mock_activities = [
                    act for act in mock_activities 
                    if act.category.value.lower() == category.lower()
                ]
            
            # Simulate trending with random boost and recency
            trending_activities = []
            for activity in mock_activities:
                trending_score = activity.rating + _SAFE_RANDOM.uniform(0, 1)
                activity_dict = activity.dict()
                activity_dict['trending_score'] = trending_score
                trending_activities.append(activity_dict)
            
            # Sort by trending score
            trending_activities.sort(key=lambda x: x['trending_score'], reverse=True)
            
            return [Activity(**act) for act in trending_activities[:limit]]
            
        except Exception as e:
            logger.error(f"Error fetching trending activities: {str(e)}")
            raise
    
    def get_similar_activities(self, activity_id: str, limit: int) -> List[Activity]:
        """Ranks a mock pool by heuristic similarity to a reference activity.

        Args:
            activity_id: Seed id resolved via ``_get_activity_by_id``.
            limit: Max neighbors to return.

        Returns:
            Closest activities by similarity, or empty if the seed is unknown.

        Raises:
            Exception: Logged and re-raised if similarity scoring fails.
        """
        try:
            # Get reference activity (mock implementation)
            reference_activity = self._get_activity_by_id(activity_id)
            if not reference_activity:
                return []
            
            # Get candidate activities
            all_activities = self._generate_mock_activities("similar", limit * 3)
            
            # Calculate similarity scores
            similar_activities = []
            for activity in all_activities:
                if activity.activity_id == activity_id:
                    continue
                
                similarity_score = self._calculate_similarity(
                    reference_activity, 
                    activity
                )
                
                activity_dict = activity.dict()
                activity_dict['similarity_score'] = similarity_score
                similar_activities.append(activity_dict)
            
            # Sort by similarity and return top matches
            similar_activities.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return [Activity(**act) for act in similar_activities[:limit]]
            
        except Exception as e:
            logger.error(f"Error fetching similar activities: {str(e)}")
            raise
    
    def record_feedback(self, user_id: str, activity_id: str, rating: int, feedback_text: Optional[str]):
        """Logs structured feedback and calls the preference-update stub.

        Args:
            user_id: Rater.
            activity_id: Target activity.
            rating: Ordinal score (1–5).
            feedback_text: Optional comment stored only in logs for now.

        Raises:
            Exception: Propagates after logging on failure.
        """
        try:
            # In production, store in database and use for model retraining
            _ = (user_id, activity_id, feedback_text)
            logger.info("Recorded recommendation feedback with rating %s", rating)
            
            # Update user preferences based on feedback
            self._update_user_preferences_from_feedback(user_id, activity_id)
            
        except Exception as e:
            logger.error(f"Error recording feedback: {str(e)}")
            raise
    
    def get_activity_categories(self) -> List[str]:
        """Lists every ``ActivityType`` enum value as a string."""
        return [category.value for category in ActivityType]

    def get_personalized_destinations(
        self, request: DestinationRecommendationRequest
    ) -> DestinationRecommendationResponse:
        """PBI 24: ranks catalog destinations with compatibility, diversity, and trend inserts.

        Scores each catalog row using preference overlap, optional success-pattern boosts,
        theme weights, and light jitter; enforces a minimum compatibility floor, applies
        diversity heuristics (e.g. beach-heavy history), and optionally prepends emerging
        destinations from ``trends_service``.

        Args:
            request: User id, theme weights, success-pattern preference, caps, and trend flag.

        Returns:
            ``DestinationRecommendationResponse`` with cards and an optional diversity note.
        """
        profile = self._get_user_profile(request.user_id)
        pref_values = {p.value for p in profile.get("preferences", [])}
        successful_tags, visited_tags = self._extract_history_tags(profile)
        scored = self._score_destination_catalog(request, pref_values, successful_tags)
        picked, diversity_note = self._select_diverse_destinations(scored, request.max_results, visited_tags)
        merged, diversity_note = self._merge_emerging_destinations(
            picked,
            diversity_note,
            pref_values,
            request.include_emerging_trends,
            request.max_results,
        )

        travel_month = request.travel_month or datetime.now(timezone.utc).month
        seasonality_note = ""
        if request.apply_seasonality_mitigation and self.seasonality_service:
            merged = self._apply_seasonality_to_destination_cards(merged, travel_month)
            seasonality_note = (
                f"Mitigación estacional activa (mes de viaje {travel_month}): "
                "scores ajustados por índice de demanda y visibilidad dinámica."
            )

        return DestinationRecommendationResponse(
            user_id=request.user_id,
            destinations=merged[: request.max_results],
            generated_at=datetime.now(timezone.utc),
            diversity_note=diversity_note.strip(),
            seasonality_note=seasonality_note,
        )

    def _apply_seasonality_to_destination_cards(
        self, cards: List[DestinationCard], month: int
    ) -> List[DestinationCard]:
        if not self.seasonality_service:
            return cards
        out: List[DestinationCard] = []
        for c in cards:
            ctx = self.seasonality_service.seasonal_context(c.destination_id, month)
            adj = min(1.0, c.compatibility_score * ctx.visibility_multiplier)
            extra = ""
            if ctx.phase == "off_peak":
                extra = (
                    f" Estacionalidad: valle/hombro (índice demanda {ctx.demand_index:.2f}); "
                    "mayor visibilidad en ranking."
                )
            elif ctx.phase == "peak":
                extra = (
                    f" Estacionalidad: pico (índice demanda {ctx.demand_index:.2f}); "
                    "visibilidad moderada para balancear capacidad."
                )
            else:
                extra = f" Estacionalidad: hombro (índice demanda {ctx.demand_index:.2f})."
            out.append(
                c.model_copy(
                    update={
                        "compatibility_score": round(adj, 4),
                        "rationale": (c.rationale + extra).strip(),
                        "seasonal_context": ctx,
                    }
                )
            )
        out.sort(key=lambda x: x.compatibility_score, reverse=True)
        return out

    def _extract_history_tags(self, profile: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        history: List[Dict[str, Any]] = profile.get("travel_history", [])
        successful_tags: List[str] = []
        visited_tags: List[str] = []
        for trip in history:
            tags = trip.get("tags", []) or []
            visited_tags.extend(tags)
            if trip.get("liked", True):
                successful_tags.extend(tags)
        return successful_tags, visited_tags

    def _score_destination_catalog(
        self,
        request: DestinationRecommendationRequest,
        pref_values: set[str],
        successful_tags: List[str],
    ) -> List[Tuple[DestinationCard, float, str]]:
        tw = request.theme_weights or {}
        scored: List[Tuple[DestinationCard, float, str]] = []
        for row in _DESTINATION_CATALOG:
            tags = row["tags"]
            base = len(pref_values & set(tags)) / max(len(pref_values | set(tags)), 1)
            success_boost = self._compute_success_boost(
                request.prefer_successful_patterns, successful_tags, tags
            )
            theme_boost = self._compute_theme_boost(tw, tags)
            score = min(
                1.0,
                0.72 * base + 0.18 + success_boost + theme_boost + _SAFE_RANDOM.uniform(0.01, 0.04),
            )
            rationale = self._build_destination_rationale(base, success_boost, theme_boost)
            card = DestinationCard(
                destination_id=row["destination_id"],
                name=row["name"],
                country=row["country"],
                tags=tags,
                compatibility_score=round(score, 4),
                rationale=rationale,
            )
            scored.append((card, score, row["destination_id"]))
        return scored

    def _compute_success_boost(
        self, prefer_success: bool, successful_tags: List[str], tags: List[str]
    ) -> float:
        if not (prefer_success and successful_tags):
            return 0.0
        return min(0.12, 0.03 * len(set(tags) & set(successful_tags)))

    def _compute_theme_boost(self, theme_weights: Dict[str, float], tags: List[str]) -> float:
        if not theme_weights:
            return 0.0
        hits = [theme_weights[t] for t in tags if t in theme_weights]
        if not hits:
            return 0.0
        return min(0.1, 0.05 * sum(hits) / len(hits))

    def _build_destination_rationale(self, base: float, success_boost: float, theme_boost: float) -> str:
        rationale = f"Alineación preferencias {base:.0%}"
        if success_boost:
            rationale += f"; refuerzo por viajes exitosos similares (+{success_boost:.0%})"
        if theme_boost:
            rationale += f"; sesgo feed/UI (+{theme_boost:.0%})"
        return rationale

    def _select_diverse_destinations(
        self,
        scored: List[Tuple[DestinationCard, float, str]],
        max_results: int,
        visited_tags: List[str],
    ) -> Tuple[List[DestinationCard], str]:
        strong = self._strong_candidates(scored, max_results)
        beach_heavy = visited_tags.count("beach") >= 2
        strong_sorted = sorted(strong, key=lambda x: x[1], reverse=True)
        picked = self._pick_primary_diverse(strong_sorted, max_results, beach_heavy)
        if beach_heavy:
            self._fill_non_beach_candidates(picked, strong_sorted, max_results)
        diversity_note = self._diversity_note(beach_heavy)
        return picked, diversity_note

    def _strong_candidates(
        self, scored: List[Tuple[DestinationCard, float, str]], max_results: int
    ) -> List[Tuple[DestinationCard, float, str]]:
        min_score = settings.DESTINATION_MIN_COMPATIBILITY
        strong = [(c, s, i) for c, s, i in scored if s >= min_score]
        if strong:
            return strong
        return sorted(scored, key=lambda x: x[1], reverse=True)[: max(1, max_results // 2)]

    def _pick_primary_diverse(
        self,
        strong_sorted: List[Tuple[DestinationCard, float, str]],
        max_results: int,
        beach_heavy: bool,
    ) -> List[DestinationCard]:
        picked: List[DestinationCard] = []
        used_tags: set[str] = set()
        for card, _, _ in strong_sorted:
            if len(picked) >= max_results:
                break
            primary = card.tags[0] if card.tags else ""
            if beach_heavy and primary == "beach" and used_tags and "beach" in used_tags:
                continue
            picked.append(card)
            used_tags.add(primary)
        return picked

    def _fill_non_beach_candidates(
        self,
        picked: List[DestinationCard],
        strong_sorted: List[Tuple[DestinationCard, float, str]],
        max_results: int,
    ) -> None:
        seen_ids = {c.destination_id for c in picked}
        for card, _, _ in strong_sorted:
            if len(picked) >= max_results:
                break
            if "beach" not in card.tags and card.destination_id not in seen_ids:
                picked.append(card)
                seen_ids.add(card.destination_id)

    def _diversity_note(self, beach_heavy: bool) -> str:
        if not beach_heavy:
            return ""
        return (
            "Se priorizó variedad respecto a destinos de playa previos, "
            "manteniendo opciones afines a experiencias que funcionaron bien."
        )

    def _merge_emerging_destinations(
        self,
        picked: List[DestinationCard],
        diversity_note: str,
        pref_values: set[str],
        include_emerging_trends: bool,
        max_results: int,
    ) -> Tuple[List[DestinationCard], str]:
        merged = list(picked)
        inserted_emerging = False
        if self.trends_service and include_emerging_trends:
            seen_ids = {c.destination_id for c in merged}
            for hit in self.trends_service.emerging_for_preferences(pref_values):
                if hit["destination_id"] in seen_ids:
                    continue
                inserted_emerging = True
                boost = min(0.08, float(hit.get("surge_ratio", 0.5)) * 0.05)
                score = min(0.99, settings.DESTINATION_MIN_COMPATIBILITY + 0.02 + boost)
                rationale = (
                    f"Tendencia emergente (volumen +{hit.get('surge_ratio', 0):.0%} vs ventana previa); "
                    "alineado con tus intereses."
                )
                merged.insert(
                    0,
                    DestinationCard(
                        destination_id=hit["destination_id"],
                        name=hit["name"],
                        country=hit["country"],
                        tags=list(hit.get("tags", [])),
                        compatibility_score=round(score, 4),
                        rationale=rationale,
                    ),
                )
                seen_ids.add(hit["destination_id"])
            if len(merged) > max_results:
                merged = merged[:max_results]
            if inserted_emerging:
                diversity_note = (diversity_note + " " if diversity_note else "") + (
                    "Se integraron destinos marcados como emergentes en el dashboard de tendencias."
                )
        return merged, diversity_note

    def get_contextual_activities(
        self, request: ContextualActivityRequest
    ) -> ContextualActivityResponse:
        """PBI 25: ranks a GPS-local pool by distance, prefs, and weather suitability.

        Adverse weather deprioritizes outdoor rows and reorders indoor-first while keeping
        a blended score of proximity, tag overlap, and indoor fitness.

        Args:
            request: User id, coordinates, radius, weather enum, and result cap.

        Returns:
            ``ContextualActivityResponse`` with ranked activities and a context note.
        """
        profile = self._get_user_profile(request.user_id)
        city = request.city_hint or "current_area"
        pool = self._generate_contextual_activity_pool(
            city,
            request.latitude,
            request.longitude,
            count=max(16, request.max_results * 3),
        )

        bad_weather = request.weather in {
            WeatherCondition.RAIN,
            WeatherCondition.STORM,
            WeatherCondition.SNOW,
            WeatherCondition.EXTREME_HEAT,
        }

        def score_act(act: Activity) -> float:
            dist = self._haversine_km(
                request.latitude, request.longitude, act.location.latitude, act.location.longitude
            )
            act.distance_km = round(dist, 2)
            dist_score = max(0.0, 1.0 - dist / max(request.radius_km, 1.0))
            tag_hits = sum(
                1 for t in act.tags if t in {p.value for p in profile.get("preferences", [])}
            )
            pref_score = min(1.0, 0.15 * tag_hits)
            weather_score = 1.0 if (not bad_weather or act.indoor) else 0.25
            return 0.45 * dist_score + 0.35 * pref_score + 0.2 * weather_score

        ranked = sorted(pool, key=score_act, reverse=True)

        if bad_weather:
            indoor_first = [a for a in ranked if a.indoor]
            outdoor_rest = [a for a in ranked if not a.indoor]
            ranked = indoor_first + outdoor_rest

        chosen = ranked[: request.max_results]
        adj = (
            "Clima adverso detectado: se priorizaron experiencias bajo techo cercanas."
            if bad_weather
            else "Condiciones favorables: se mezclaron actividades indoor y outdoor cercanas."
        )

        return ContextualActivityResponse(
            user_id=request.user_id,
            location_summary=f"{city} ({request.latitude:.3f}, {request.longitude:.3f})",
            weather=request.weather,
            activities=chosen,
            context_adjustment=adj,
            generated_at=datetime.now(timezone.utc),
        )

    # Private helper methods

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in kilometers between two WGS84 points."""
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    def _generate_contextual_activity_pool(
        self, city: str, center_lat: float, center_lon: float, count: int
    ) -> List[Activity]:
        """Activities anchored near GPS with indoor flags for contextual ranking."""
        activities: List[Activity] = []
        categories = list(ActivityType)
        preferences = list(TravelPreference)
        indoor_categories = {
            ActivityType.FOOD,
            ActivityType.ENTERTAINMENT,
            ActivityType.WELLNESS,
            ActivityType.SHOPPING,
            ActivityType.CULTURAL,
            ActivityType.EDUCATION,
        }

        for i in range(count):
            cat = _SAFE_RANDOM.choice(categories)
            indoor = cat in indoor_categories or _SAFE_RANDOM.random() < 0.35
            lat = center_lat + _SAFE_RANDOM.uniform(-0.08, 0.08)
            lon = center_lon + _SAFE_RANDOM.uniform(-0.08, 0.08)
            activities.append(
                Activity(
                    activity_id=f"ctx_{city}_{i}",
                    name=f"Experiencia contextual {i + 1}",
                    category=cat,
                    description=f"Actividad sugerida cerca de tu posición en {city}",
                    location=Location(
                        latitude=lat,
                        longitude=lon,
                        city=city,
                        country="",
                        radius_km=5.0,
                    ),
                    rating=_SAFE_RANDOM.uniform(3.8, 5.0),
                    price_range=_SAFE_RANDOM.choice(["$", "$$", "$$$"]),
                    duration_hours=_SAFE_RANDOM.uniform(1.0, 6.0),
                    tags=[_SAFE_RANDOM.choice([p.value for p in preferences]) for _ in range(3)],
                    requirements=[],
                    best_time_to_visit="Hoy",
                    images=[],
                    indoor=indoor,
                )
            )
        return activities

    def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Mock profile dict with preferences, travel history tags, and budget."""
        # Mock implementation - in production, query database / core backend
        return {
            "user_id": user_id,
            "preferences": [TravelPreference.CULTURAL, TravelPreference.FOODIE, TravelPreference.BEACH],
            "travel_history": [
                {
                    "destination": "Cancún",
                    "tags": ["beach", "relaxation"],
                    "liked": True,
                },
                {
                    "destination": "Lisboa",
                    "tags": ["cultural", "foodie"],
                    "liked": True,
                },
                {
                    "destination": "Tulum",
                    "tags": ["beach", "nature"],
                    "liked": False,
                },
            ],
            "location": "New York",
            "budget_range": {"min": 50, "max": 200},
        }
    
    def _get_candidate_activities(self, request: RecommendationRequest) -> List[Activity]:
        """Builds an oversized mock pool from the request city for downstream scoring."""
        # Mock implementation - in production, query database with location filters
        return self._generate_mock_activities(request.location.city or "Unknown", request.max_results * 3)
    
    def _score_activities(self, activities: List[Activity], user_profile: Dict[str, Any], request: RecommendationRequest) -> List[Dict[str, Any]]:
        """Heuristic blend of rating, tag/pref overlap, budget hints, and group size."""
        scored_activities = []
        user_preferences = request.preferences or user_profile.get("preferences", [])

        for activity in activities:
            score = 0.0
            
            # Base score from rating
            score += activity.rating * 0.3
            
            # Preference matching
            for pref in user_preferences:
                if pref.value in [tag.lower() for tag in activity.tags]:
                    score += 0.4
            
            # Location proximity (mock calculation)
            score += _SAFE_RANDOM.uniform(0.1, 0.3) * 0.2
            
            # Price range matching
            budget = user_profile.get('budget_range', {})
            if budget:
                # Simple price matching logic
                score += _SAFE_RANDOM.uniform(0.1, 0.2) * 0.1
            if request.budget_limit is not None:
                score += min(0.08, float(request.budget_limit) / 10000.0)
            if request.group_size is not None and request.group_size > 1:
                score += 0.03

            activity_dict = activity.dict()
            activity_dict['confidence_score'] = min(score, 1.0)
            scored_activities.append(activity_dict)
        
        return scored_activities
    
    def _apply_ranking_and_diversity(self, scored_activities: List[Dict[str, Any]], max_results: int) -> List[Activity]:
        """Sorts by confidence then caps per-category representation for variety."""
        # Sort by confidence score
        scored_activities.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Apply diversity - ensure different categories are represented
        diverse_recommendations = []
        category_counts = {}
        
        for activity in scored_activities:
            category = activity['category']
            if category not in category_counts:
                category_counts[category] = 0
            
            # Limit activities per category for diversity
            if category_counts[category] < max(2, max_results // 3):
                diverse_recommendations.append(Activity(**activity))
                category_counts[category] += 1
                
                if len(diverse_recommendations) >= max_results:
                    break
        
        return diverse_recommendations
    
    def _generate_explanation(self, recommendations: List[Activity], user_profile: Dict[str, Any]) -> str:
        """Template string summarizing top user prefs and recommended categories."""
        if not recommendations:
            return "No recommendations available at the moment."
        
        categories = list({rec.category.value for rec in recommendations})
        user_prefs = [pref.value for pref in user_profile.get('preferences', [])]
        
        explanation = f"Based on your interest in {', '.join(user_prefs[:3])}, "
        explanation += f"I recommend these {', '.join(categories[:3])} activities. "
        explanation += "These match your preferences and have high ratings from similar travelers."
        
        return explanation
    
    def _generate_mock_activities(self, location: str, count: int) -> List[Activity]:
        """Synthetic activities with random geo, tags, indoor flags, and ratings."""
        activities = []
        categories = list(ActivityType)
        preferences = list(TravelPreference)
        
        indoor_cats = {
            ActivityType.FOOD,
            ActivityType.ENTERTAINMENT,
            ActivityType.WELLNESS,
            ActivityType.SHOPPING,
            ActivityType.CULTURAL,
            ActivityType.EDUCATION,
        }
        safe_count = max(1, min(int(count), 200))
        for i in range(safe_count):
            cat = _SAFE_RANDOM.choice(categories)
            activity = Activity(
                activity_id=f"activity_{location}_{i}",
                name=f"Activity {i+1} in {location}",
                category=cat,
                description=f"Amazing activity {i+1} in {location} with great experiences",
                location=Location(
                    latitude=_SAFE_RANDOM.uniform(-90, 90),
                    longitude=_SAFE_RANDOM.uniform(-180, 180),
                    city=location,
                    country="Country",
                    radius_km=10.0
                ),
                rating=_SAFE_RANDOM.uniform(3.0, 5.0),
                price_range=_SAFE_RANDOM.choice(["$", "$$", "$$$", "$$$$"]),
                duration_hours=_SAFE_RANDOM.uniform(1, 8),
                tags=[_SAFE_RANDOM.choice([pref.value for pref in preferences]) for _ in range(3)],
                requirements=[],
                best_time_to_visit="Any time",
                images=[],
                indoor=cat in indoor_cats or _SAFE_RANDOM.random() < 0.25,
            )
            activities.append(activity)
        
        return activities
    
    def _get_activity_by_id(self, activity_id: str) -> Optional[Activity]:
        """Linear scan over a generated mock batch to resolve an id."""
        # Mock implementation - in production, query database
        activities = self._generate_mock_activities("test", 100)
        for activity in activities:
            if activity.activity_id == activity_id:
                return activity
        return None
    
    def _calculate_similarity(self, activity1: Activity, activity2: Activity) -> float:
        """Weighted mix of category match, Jaccard tags, price band, and rating proximity."""
        similarity = 0.0
        
        # Category similarity
        if activity1.category == activity2.category:
            similarity += 0.4
        
        # Tag similarity
        tags1 = set(activity1.tags)
        tags2 = set(activity2.tags)
        if tags1 and tags2:
            tag_similarity = len(tags1.intersection(tags2)) / len(tags1.union(tags2))
            similarity += tag_similarity * 0.3
        
        # Price range similarity
        if activity1.price_range == activity2.price_range:
            similarity += 0.2
        
        # Rating similarity
        rating_diff = abs(activity1.rating - activity2.rating)
        rating_similarity = 1 - (rating_diff / 5.0)
        similarity += rating_similarity * 0.1
        
        return min(similarity, 1.0)
    
    def _update_user_preferences_from_feedback(self, user_id: str, activity_id: str):
        """Placeholder hook for future preference learning from ratings."""
        # In production, implement preference learning algorithm
        _ = (user_id, activity_id)
        logger.info("Updating user preferences from recommendation feedback")
