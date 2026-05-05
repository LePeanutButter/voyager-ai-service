"""
Behavior Analysis Service for implicit user preference learning.

Analyzes user interaction patterns to automatically update user preferences
and improve recommendation accuracy without explicit user input.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import statistics

from app.modules.common.schemas.base import DateRange
from app.modules.common.schemas.enums import InteractionType, TravelPreference
from app.modules.behavior.schemas import (
    BehaviorTrackingRequest,
    BehaviorAnalysisRequest,
    BehaviorPattern,
    ImplicitPreferenceUpdate,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class BehaviorAnalysisService:
    """Service for analyzing user behavior and updating preferences implicitly."""
    
    def __init__(self, model_manager=None):
        """Initialize with optional ML model manager."""
        self.model_manager = model_manager
        self.behavior_data = {}  # In-memory storage (replace with database in production)
        self.preference_weights = {
            InteractionType.VIEW: 0.1,
            InteractionType.CLICK: 0.2,
            InteractionType.BOOKMARK: 0.5,
            InteractionType.SHARE: 0.4,
            InteractionType.REJECT: -0.6,
            InteractionType.BOOK: 0.8,
            InteractionType.RATE: 0.7,
            InteractionType.SEARCH: 0.3,
            InteractionType.FILTER: 0.2
        }
        
        # Pattern detection thresholds
        self.REJECTION_THRESHOLD = 3  # Number of rejections to detect pattern
        self.PREFERENCE_CONFIDENCE_THRESHOLD = 0.7
        self.MIN_INTERACTIONS_FOR_ANALYSIS = 5
    
    async def track_interaction(self, request: BehaviorTrackingRequest) -> bool:
        """
        Track a user interaction for behavior analysis.
        
        Args:
            request: Behavior tracking request
            
        Returns:
            True if tracking successful
        """
        try:
            user_id = request.user_id
            
            # Initialize user behavior data if not exists
            if user_id not in self.behavior_data:
                self.behavior_data[user_id] = {
                    'interactions': [],
                    'patterns': [],
                    'last_analysis': None
                }
            
            # Store interaction
            interaction = {
                'interaction_type': request.interaction_type,
                'activity_id': request.activity_id,
                'activity_category': request.activity_category,
                'session_duration': request.session_duration,
                'context': request.context,
                'timestamp': datetime.now(timezone.utc)
            }
            
            self.behavior_data[user_id]['interactions'].append(interaction)
            
            # Keep only recent interactions (last 30 days)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            self.behavior_data[user_id]['interactions'] = [
                i for i in self.behavior_data[user_id]['interactions']
                if i['timestamp'] > cutoff_date
            ]
            
            logger.info(f"Tracked {request.interaction_type} interaction for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error tracking interaction: {str(e)}")
            return False
    
    async def analyze_behavior(self, request: BehaviorAnalysisRequest) -> ImplicitPreferenceUpdate:
        """
        Analyze user behavior patterns and generate preference updates.
        
        Args:
            request: Behavior analysis request
            
        Returns:
            Implicit preference update with detected patterns
        """
        try:
            user_id = request.user_id
            
            if user_id not in self.behavior_data:
                raise ValueError(f"No behavior data found for user {user_id}")
            
            user_data = self.behavior_data[user_id]
            interactions = user_data['interactions']
            
            # Filter interactions by analysis period
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=request.analysis_period_days)
            recent_interactions = [
                i for i in interactions 
                if i['timestamp'] > cutoff_date
            ]
            
            if len(recent_interactions) < self.MIN_INTERACTIONS_FOR_ANALYSIS:
                logger.warning(f"Insufficient interactions for user {user_id}: {len(recent_interactions)}")
                return self._create_empty_update(user_id, request.analysis_period_days)
            
            # Detect patterns
            patterns = []
            if request.include_patterns:
                patterns = await self._detect_behavior_patterns(recent_interactions)
            
            # Calculate preference updates
            preference_changes = {}
            if request.include_preference_updates:
                preference_changes = await self._calculate_preference_updates(recent_interactions, patterns)
            
            # Create analysis period
            analysis_period = DateRange(
                start=cutoff_date,
                end=datetime.now(timezone.utc)
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(recent_interactions, patterns)
            
            # Update last analysis timestamp
            user_data['last_analysis'] = datetime.now(timezone.utc)
            
            return ImplicitPreferenceUpdate(
                user_id=user_id,
                preference_changes=preference_changes,
                detected_patterns=patterns,
                analysis_period=analysis_period,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            logger.error(f"Error analyzing behavior for user {request.user_id}: {str(e)}")
            raise
    
    async def _detect_behavior_patterns(self, interactions: List[Dict]) -> List[BehaviorPattern]:
        """Detect behavior patterns from user interactions."""
        patterns = []
        
        # Pattern 1: Consistent rejection of certain categories
        rejection_patterns = self._detect_rejection_patterns(interactions)
        patterns.extend(rejection_patterns)
        
        # Pattern 2: Preference for specific activity types
        preference_patterns = self._detect_preference_patterns(interactions)
        patterns.extend(preference_patterns)
        
        # Pattern 3: Time-based preferences
        time_patterns = self._detect_time_based_patterns(interactions)
        patterns.extend(time_patterns)
        
        # Pattern 4: Budget sensitivity
        budget_patterns = self._detect_budget_patterns(interactions)
        patterns.extend(budget_patterns)
        
        return patterns
    
    def _detect_rejection_patterns(self, interactions: List[Dict]) -> List[BehaviorPattern]:
        """Detect patterns of consistent rejection."""
        patterns = []
        
        # Count rejections by category
        category_rejections = Counter()
        for interaction in interactions:
            if interaction['interaction_type'] == InteractionType.REJECT:
                category = interaction.get('activity_category', 'unknown')
                category_rejections[category] += 1
        
        # Create patterns for significant rejections
        for category, count in category_rejections.items():
            if count >= self.REJECTION_THRESHOLD:
                confidence = min(count / (self.REJECTION_THRESHOLD * 2), 1.0)
                pattern = BehaviorPattern(
                    pattern_type=f"rejection_pattern_{category}",
                    confidence=confidence,
                    frequency=count,
                    last_detected=datetime.now(timezone.utc),
                    context={"category": category, "rejection_count": count}
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_preference_patterns(self, interactions: List[Dict]) -> List[BehaviorPattern]:
        """Detect strong preference patterns."""
        patterns = []
        
        # Count positive interactions by category
        category_preferences = defaultdict(lambda: {'positive': 0, 'total': 0})
        
        for interaction in interactions:
            category = interaction.get('activity_category', 'unknown')
            weight = self.preference_weights.get(interaction['interaction_type'], 0)
            
            category_preferences[category]['total'] += 1
            if weight > 0:
                category_preferences[category]['positive'] += weight
        
        # Identify strong preferences
        for category, data in category_preferences.items():
            if data['total'] >= 3:  # Minimum interactions
                preference_ratio = data['positive'] / data['total']
                if preference_ratio >= 0.7:  # Strong preference threshold
                    pattern = BehaviorPattern(
                        pattern_type=f"preference_pattern_{category}",
                        confidence=preference_ratio,
                        frequency=data['total'],
                        last_detected=datetime.now(timezone.utc),
                        context={
                            "category": category,
                            "preference_ratio": preference_ratio,
                            "interaction_count": data['total']
                        }
                    )
                    patterns.append(pattern)
        
        return patterns
    
    def _detect_time_based_patterns(self, interactions: List[Dict]) -> List[BehaviorPattern]:
        """Detect time-based interaction patterns."""
        patterns = []
        
        # Analyze interaction times
        hour_counts = Counter()
        for interaction in interactions:
            hour = interaction['timestamp'].hour
            hour_counts[hour] += 1
        
        # Find peak hours
        if len(hour_counts) > 0:
            peak_hour = hour_counts.most_common(1)[0][0]
            peak_count = hour_counts[peak_hour]
            total_interactions = len(interactions)
            
            if peak_count >= total_interactions * 0.2:  # At least 20% of interactions
                pattern = BehaviorPattern(
                    pattern_type="time_preference_pattern",
                    confidence=peak_count / total_interactions,
                    frequency=peak_count,
                    last_detected=datetime.now(timezone.utc),
                    context={
                        "peak_hour": peak_hour,
                        "interaction_percentage": peak_count / total_interactions
                    }
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_budget_patterns(self, interactions: List[Dict]) -> List[BehaviorPattern]:
        """Detect budget-related patterns."""
        patterns = []
        
        # Analyze price range preferences from context
        price_preferences = []
        for interaction in interactions:
            context = interaction.get('context', {})
            if 'price_range' in context:
                price_preferences.append(context['price_range'])
        
        if len(price_preferences) >= 3:
            # Find most common price range
            price_counter = Counter(price_preferences)
            common_price = price_counter.most_common(1)[0][0]
            price_ratio = price_counter[common_price] / len(price_preferences)
            
            if price_ratio >= 0.6:  # Strong preference
                pattern = BehaviorPattern(
                    pattern_type="budget_preference_pattern",
                    confidence=price_ratio,
                    frequency=price_counter[common_price],
                    last_detected=datetime.now(timezone.utc),
                    context={
                        "preferred_price_range": common_price,
                        "preference_ratio": price_ratio
                    }
                )
                patterns.append(pattern)
        
        return patterns
    
    async def _calculate_preference_updates(self, interactions: List[Dict], patterns: List[BehaviorPattern]) -> Dict[str, float]:
        """Calculate preference updates based on interactions and patterns."""
        preference_updates = {}
        
        # Calculate category-based preference updates
        category_scores = defaultdict(float)
        for interaction in interactions:
            category = interaction.get('activity_category', 'unknown')
            weight = self.preference_weights.get(interaction['interaction_type'], 0)
            category_scores[category] += weight
        
        # Normalize scores
        max_score = max(abs(score) for score in category_scores.values()) if category_scores else 1
        if max_score > 0:
            for category, score in category_scores.items():
                normalized_score = score / max_score
                if abs(normalized_score) >= 0.3:  # Only include significant updates
                    preference_updates[category] = normalized_score
        
        # Apply pattern-based adjustments
        for pattern in patterns:
            if pattern.pattern_type.startswith("rejection_pattern_"):
                category = pattern.context.get("category", "unknown")
                preference_updates[category] = preference_updates.get(category, 0) - pattern.confidence
            elif pattern.pattern_type.startswith("preference_pattern_"):
                category = pattern.context.get("category", "unknown")
                preference_updates[category] = preference_updates.get(category, 0) + pattern.confidence * 0.5
        
        return preference_updates
    
    def _calculate_confidence_score(self, interactions: List[Dict], patterns: List[BehaviorPattern]) -> float:
        """Calculate overall confidence in the analysis."""
        # Base confidence on interaction count
        interaction_confidence = min(len(interactions) / 20.0, 1.0)  # Max confidence at 20 interactions
        
        # Pattern confidence
        pattern_confidence = 0
        if patterns:
            pattern_confidence = statistics.mean([p.confidence for p in patterns])
        
        # Combined confidence
        overall_confidence = (interaction_confidence * 0.6) + (pattern_confidence * 0.4)
        return min(overall_confidence, 1.0)
    
    def _create_empty_update(self, user_id: str, analysis_days: int) -> ImplicitPreferenceUpdate:
        """Create empty preference update when insufficient data."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=analysis_days)
        analysis_period = DateRange(
            start=cutoff_date,
            end=datetime.now(timezone.utc)
        )
        
        return ImplicitPreferenceUpdate(
            user_id=user_id,
            preference_changes={},
            detected_patterns=[],
            analysis_period=analysis_period,
            confidence_score=0.0
        )
    
    async def get_user_behavior_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get a summary of user's behavior patterns."""
        if user_id not in self.behavior_data:
            return {"error": "No behavior data found"}
        
        interactions = self.behavior_data[user_id]['interactions']
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        recent_interactions = [i for i in interactions if i['timestamp'] > cutoff_date]
        
        # Interaction statistics
        interaction_counts = Counter([i['interaction_type'] for i in recent_interactions])
        category_counts = Counter([i.get('activity_category', 'unknown') for i in recent_interactions])
        
        # Recent patterns
        recent_patterns = self.behavior_data[user_id].get('patterns', [])[-5:]  # Last 5 patterns
        
        return {
            "user_id": user_id,
            "analysis_period_days": days,
            "total_interactions": len(recent_interactions),
            "interaction_breakdown": dict(interaction_counts),
            "category_breakdown": dict(category_counts),
            "recent_patterns": [p.dict() for p in recent_patterns],
            "last_analysis": self.behavior_data[user_id].get('last_analysis')
        }
