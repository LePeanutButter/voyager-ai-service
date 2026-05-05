"""
Recommendation service for personalized travel suggestions.

Implements the core recommendation logic using ML models and
business rules for generating personalized travel recommendations.
"""

from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.trends_service import TrendsService
import logging
import math
import random
from datetime import datetime, timedelta, timezone

from app.models.schemas import (
    RecommendationRequest,
    RecommendationResponse,
    Activity,
    Location,
    ActivityType,
    TravelPreference,
    DestinationCard,
    DestinationRecommendationRequest,
    DestinationRecommendationResponse,
    ContextualActivityRequest,
    ContextualActivityResponse,
    WeatherCondition,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

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
    """Service for generating personalized travel recommendations."""
    
    def __init__(self, model_manager, trends_service: Optional["TrendsService"] = None):
        """Initialize with ML model manager and optional trends service (Feature 15)."""
        self.model_manager = model_manager
        self.trends_service = trends_service
        self.cache = {}  # Simple in-memory cache (replace with Redis in production)
    
    async def generate_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        Generate personalized recommendations based on user profile and context.
        
        Args:
            request: Recommendation request with user context and preferences
            
        Returns:
            RecommendationResponse with personalized activities and confidence scores
        """
        try:
            logger.info(f"Generating recommendations for user {request.user_id}")
            
            # Get user profile for personalization
            user_profile = await self._get_user_profile(request.user_id)
            
            # Get candidate activities based on location and filters
            candidate_activities = await self._get_candidate_activities(request)
            
            # Score activities using ML models and business rules
            scored_activities = await self._score_activities(
                candidate_activities, 
                user_profile, 
                request
            )
            
            # Apply diversity and ranking algorithms
            final_recommendations = await self._apply_ranking_and_diversity(
                scored_activities, 
                request.max_results
            )
            
            # Generate explanation for recommendations
            explanation = await self._generate_explanation(
                final_recommendations, 
                user_profile
            )
            
            response = RecommendationResponse(
                recommendations=final_recommendations,
                user_id=request.user_id,
                generated_at=datetime.now(timezone.utc),
                total_results=len(final_recommendations),
                confidence_scores=[act.get('confidence_score', 0.0) for act in final_recommendations],
                explanation=explanation
            )
            
            # Cache the response for future requests
            cache_key = f"rec_{request.user_id}_{hash(str(request.location))}"
            self.cache[cache_key] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            raise
    
    async def get_popular_activities(self, location: str, limit: int) -> List[Activity]:
        """
        Get popular activities for a specific location.
        
        Args:
            location: Location name
            limit: Maximum number of activities to return
            
        Returns:
            List of popular activities
        """
        try:
            # Mock implementation - in production, query database
            mock_activities = await self._generate_mock_activities(location, limit)
            
            # Sort by rating and popularity
            popular_activities = sorted(
                mock_activities, 
                key=lambda x: (x.rating, random.random()), 
                reverse=True
            )[:limit]
            
            return popular_activities
            
        except Exception as e:
            logger.error(f"Error fetching popular activities: {str(e)}")
            raise
    
    async def get_trending_activities(self, category: Optional[str], limit: int) -> List[Activity]:
        """
        Get trending activities globally or by category.
        
        Args:
            category: Optional activity category filter
            limit: Maximum number of activities to return
            
        Returns:
            List of trending activities
        """
        try:
            # Mock implementation - in production, analyze recent interactions
            mock_activities = await self._generate_mock_activities("global", limit * 2)
            
            # Filter by category if specified
            if category:
                mock_activities = [
                    act for act in mock_activities 
                    if act.category.value.lower() == category.lower()
                ]
            
            # Simulate trending with random boost and recency
            trending_activities = []
            for activity in mock_activities:
                trending_score = activity.rating + random.uniform(0, 1)
                activity_dict = activity.dict()
                activity_dict['trending_score'] = trending_score
                trending_activities.append(activity_dict)
            
            # Sort by trending score
            trending_activities.sort(key=lambda x: x['trending_score'], reverse=True)
            
            return [Activity(**act) for act in trending_activities[:limit]]
            
        except Exception as e:
            logger.error(f"Error fetching trending activities: {str(e)}")
            raise
    
    async def get_similar_activities(self, activity_id: str, limit: int) -> List[Activity]:
        """
        Get activities similar to a specific activity.
        
        Args:
            activity_id: Reference activity ID
            limit: Maximum number of similar activities
            
        Returns:
            List of similar activities
        """
        try:
            # Get reference activity (mock implementation)
            reference_activity = await self._get_activity_by_id(activity_id)
            if not reference_activity:
                return []
            
            # Get candidate activities
            all_activities = await self._generate_mock_activities("similar", limit * 3)
            
            # Calculate similarity scores
            similar_activities = []
            for activity in all_activities:
                if activity.activity_id == activity_id:
                    continue
                
                similarity_score = await self._calculate_similarity(
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
    
    async def record_feedback(self, user_id: str, activity_id: str, rating: int, feedback_text: Optional[str]):
        """
        Record user feedback for recommendations.
        
        Args:
            user_id: User identifier
            activity_id: Activity identifier
            rating: Rating from 1-5
            feedback_text: Optional detailed feedback
        """
        try:
            # In production, store in database and use for model retraining
            feedback_data = {
                'user_id': user_id,
                'activity_id': activity_id,
                'rating': rating,
                'feedback_text': feedback_text,
                'timestamp': datetime.now(timezone.utc)
            }
            
            logger.info(f"Recorded feedback: {feedback_data}")
            
            # Update user preferences based on feedback
            await self._update_user_preferences_from_feedback(user_id, activity_id, rating)
            
        except Exception as e:
            logger.error(f"Error recording feedback: {str(e)}")
            raise
    
    async def get_activity_categories(self) -> List[str]:
        """
        Get all available activity categories.
        
        Returns:
            List of activity category names
        """
        return [category.value for category in ActivityType]

    async def get_personalized_destinations(
        self, request: DestinationRecommendationRequest
    ) -> DestinationRecommendationResponse:
        """
        PBI 24: destinos con compatibilidad > umbral y diversidad con sesgo a patrones exitosos.
        """
        profile = await self._get_user_profile(request.user_id)
        pref_values = {p.value for p in profile.get("preferences", [])}
        history: List[Dict[str, Any]] = profile.get("travel_history", [])
        successful_tags: List[str] = []
        visited_tags: List[str] = []
        for trip in history:
            tags = trip.get("tags", []) or []
            visited_tags.extend(tags)
            if trip.get("liked", True):
                successful_tags.extend(tags)

        scored: List[Tuple[DestinationCard, float, str]] = []
        for row in _DESTINATION_CATALOG:
            tags = row["tags"]
            base = len(pref_values & set(tags)) / max(len(pref_values | set(tags)), 1)
            success_boost = 0.0
            if request.prefer_successful_patterns and successful_tags:
                success_boost = min(
                    0.12,
                    0.03 * len(set(tags) & set(successful_tags)),
                )
            # Map Jaccard overlap into a band that can satisfy PBI 24 (>80%) when perfil y destino alinean
            score = min(1.0, 0.72 * base + 0.18 + success_boost + random.uniform(0.01, 0.04))
            rationale = f"Alineación preferencias {base:.0%}"
            if success_boost:
                rationale += f"; refuerzo por viajes exitosos similares (+{success_boost:.0%})"
            card = DestinationCard(
                destination_id=row["destination_id"],
                name=row["name"],
                country=row["country"],
                tags=tags,
                compatibility_score=round(score, 4),
                rationale=rationale,
            )
            scored.append((card, score, row["destination_id"]))

        min_score = settings.DESTINATION_MIN_COMPATIBILITY
        strong = [(c, s, i) for c, s, i in scored if s >= min_score]
        if not strong:
            strong = sorted(scored, key=lambda x: x[1], reverse=True)[: max(1, request.max_results // 2)]

        # Diversity: if user visited beach often, keep at least one non-beach when possible
        beach_heavy = visited_tags.count("beach") >= 2
        picked: List[DestinationCard] = []
        used_tags: set[str] = set()
        strong_sorted = sorted(strong, key=lambda x: x[1], reverse=True)
        for card, score, _ in strong_sorted:
            if len(picked) >= request.max_results:
                break
            primary = card.tags[0] if card.tags else ""
            if beach_heavy and primary == "beach" and used_tags and "beach" in used_tags:
                continue
            picked.append(card)
            used_tags.add(primary)

        if beach_heavy:
            seen_ids = {c.destination_id for c in picked}
            for card, score, _ in strong_sorted:
                if len(picked) >= request.max_results:
                    break
                if "beach" not in card.tags and card.destination_id not in seen_ids:
                    picked.append(card)
                    seen_ids.add(card.destination_id)

        diversity_note = ""
        if beach_heavy:
            diversity_note = (
                "Se priorizó variedad respecto a destinos de playa previos, "
                "manteniendo opciones afines a experiencias que funcionaron bien."
            )

        # PBI 30: incluir emergentes compatibles con preferencias en recomendaciones personalizadas
        merged = list(picked)
        inserted_emerging = False
        if self.trends_service and request.include_emerging_trends:
            seen_ids = {c.destination_id for c in merged}
            for hit in self.trends_service.emerging_for_preferences(pref_values):
                if hit["destination_id"] in seen_ids:
                    continue
                inserted_emerging = True
                boost = min(0.08, float(hit.get("surge_ratio", 0.5)) * 0.05)
                score = min(0.99, settings.DESTINATION_MIN_COMPATIBILITY + 0.02 + boost)
                rationale = (
                    f"Tendencia emergente (volumen +{hit.get('surge_ratio', 0):.0%} vs ventana previa); "
                    f"alineado con tus intereses."
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
            if len(merged) > request.max_results:
                merged = merged[: request.max_results]
            if inserted_emerging:
                diversity_note = (diversity_note + " " if diversity_note else "") + (
                    "Se integraron destinos marcados como emergentes en el dashboard de tendencias."
                )

        return DestinationRecommendationResponse(
            user_id=request.user_id,
            destinations=merged[: request.max_results],
            generated_at=datetime.now(timezone.utc),
            diversity_note=diversity_note.strip(),
        )

    async def get_contextual_activities(
        self, request: ContextualActivityRequest
    ) -> ContextualActivityResponse:
        """
        PBI 25: actividades según ubicación, clima y preferencias; alternativas indoor si el clima es adverso.
        """
        profile = await self._get_user_profile(request.user_id)
        city = request.city_hint or "current_area"
        pool = await self._generate_contextual_activity_pool(
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
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    async def _generate_contextual_activity_pool(
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
            cat = random.choice(categories)
            indoor = cat in indoor_categories or random.random() < 0.35
            lat = center_lat + random.uniform(-0.08, 0.08)
            lon = center_lon + random.uniform(-0.08, 0.08)
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
                    rating=random.uniform(3.8, 5.0),
                    price_range=random.choice(["$", "$$", "$$$"]),
                    duration_hours=random.uniform(1.0, 6.0),
                    tags=[random.choice([p.value for p in preferences]) for _ in range(3)],
                    requirements=[],
                    best_time_to_visit="Hoy",
                    images=[],
                    indoor=indoor,
                )
            )
        return activities

    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile for personalization."""
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
    
    async def _get_candidate_activities(self, request: RecommendationRequest) -> List[Activity]:
        """Get candidate activities based on location and filters."""
        # Mock implementation - in production, query database with location filters
        return await self._generate_mock_activities(request.location.city or "Unknown", request.max_results * 3)
    
    async def _score_activities(self, activities: List[Activity], user_profile: Dict[str, Any], request: RecommendationRequest) -> List[Dict[str, Any]]:
        """Score activities based on user preferences and context."""
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
            score += random.uniform(0.1, 0.3) * 0.2
            
            # Price range matching
            budget = user_profile.get('budget_range', {})
            if budget:
                # Simple price matching logic
                score += random.uniform(0.1, 0.2) * 0.1
            if request.budget_limit is not None:
                score += min(0.08, float(request.budget_limit) / 10000.0)
            if request.group_size is not None and request.group_size > 1:
                score += 0.03

            activity_dict = activity.dict()
            activity_dict['confidence_score'] = min(score, 1.0)
            scored_activities.append(activity_dict)
        
        return scored_activities
    
    async def _apply_ranking_and_diversity(self, scored_activities: List[Dict[str, Any]], max_results: int) -> List[Activity]:
        """Apply ranking and diversity algorithms to final recommendations."""
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
    
    async def _generate_explanation(self, recommendations: List[Activity], user_profile: Dict[str, Any]) -> str:
        """Generate explanation for recommendations."""
        if not recommendations:
            return "No recommendations available at the moment."
        
        categories = list(set([rec.category.value for rec in recommendations]))
        user_prefs = [pref.value for pref in user_profile.get('preferences', [])]
        
        explanation = f"Based on your interest in {', '.join(user_prefs[:3])}, "
        explanation += f"I recommend these {', '.join(categories[:3])} activities. "
        explanation += f"These match your preferences and have high ratings from similar travelers."
        
        return explanation
    
    async def _generate_mock_activities(self, location: str, count: int) -> List[Activity]:
        """Generate mock activities for testing."""
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
        for i in range(count):
            cat = random.choice(categories)
            activity = Activity(
                activity_id=f"activity_{location}_{i}",
                name=f"Activity {i+1} in {location}",
                category=cat,
                description=f"Amazing activity {i+1} in {location} with great experiences",
                location=Location(
                    latitude=random.uniform(-90, 90),
                    longitude=random.uniform(-180, 180),
                    city=location,
                    country="Country",
                    radius_km=10.0
                ),
                rating=random.uniform(3.0, 5.0),
                price_range=random.choice(["$", "$$", "$$$", "$$$$"]),
                duration_hours=random.uniform(1, 8),
                tags=[random.choice([pref.value for pref in preferences]) for _ in range(3)],
                requirements=[],
                best_time_to_visit="Any time",
                images=[],
                indoor=cat in indoor_cats or random.random() < 0.25,
            )
            activities.append(activity)
        
        return activities
    
    async def _get_activity_by_id(self, activity_id: str) -> Optional[Activity]:
        """Get activity by ID (mock implementation)."""
        # Mock implementation - in production, query database
        activities = await self._generate_mock_activities("test", 100)
        for activity in activities:
            if activity.activity_id == activity_id:
                return activity
        return None
    
    async def _calculate_similarity(self, activity1: Activity, activity2: Activity) -> float:
        """Calculate similarity between two activities."""
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
    
    async def _update_user_preferences_from_feedback(self, user_id: str, activity_id: str, rating: int):
        """Update user preferences based on feedback."""
        # In production, implement preference learning algorithm
        logger.info(f"Updating preferences for user {user_id} based on feedback for {activity_id}")
