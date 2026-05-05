"""
In-memory continuous learning for traveler matching (PBI 27).

Reinforces dimension weights after successful connections and dampens
weights associated with incompatible reports. Replace with persistent
store + batch training in production.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS: Dict[str, float] = {
    "interests": 0.25,
    "travel_style": 0.25,
    "budget": 0.20,
    "pace": 0.15,
    "personality": 0.15,
}

LEARNING_RATE = 0.04
DECAY_RATE = 0.03
MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.45


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(v, 1e-6) for v in weights.values())
    return {k: round(v / total, 4) for k, v in weights.items()}


@dataclass
class MatchingLearningStore:
    """Tracks feedback-derived weights for multidimensional matching."""

    weights: Dict[str, float] = field(default_factory=lambda: copy.deepcopy(DEFAULT_WEIGHTS))
    outcomes: List[Dict[str, Any]] = field(default_factory=list)

    def get_weights(self) -> Dict[str, float]:
        return _normalize(self.weights)

    def record_rating_feedback(self, rating: int) -> None:
        """Nudge weights slightly from star ratings (1–5)."""
        delta = (rating - 3) * 0.005
        for key in self.weights:
            self.weights[key] = max(MIN_WEIGHT, min(MAX_WEIGHT, self.weights[key] + delta * 0.2))
        self.weights = _normalize(self.weights)

    def record_success(
        self,
        dimension_snapshot: Optional[Dict[str, float]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, float]:
        """Reinforce dimensions that contributed to a successful connection."""
        snap = dimension_snapshot or {}
        w = self.weights
        for dim, score in snap.items():
            if dim not in w:
                continue
            boost = LEARNING_RATE * max(0.0, min(1.0, score))
            w[dim] = min(MAX_WEIGHT, w[dim] + boost)
        self.weights = _normalize(w)
        self._append_outcome("success", snap, notes)
        logger.info("Matching learning: reinforced weights after success %s", self.weights)
        return self.get_weights()

    def record_incompatible(
        self,
        dimension_snapshot: Optional[Dict[str, float]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, float]:
        """Reduce influence of dimensions that were high yet led to incompatibility."""
        snap = dimension_snapshot or {}
        w = self.weights
        for dim, score in snap.items():
            if dim not in w:
                continue
            if score >= 0.55:
                penalty = DECAY_RATE * score
                w[dim] = max(MIN_WEIGHT, w[dim] - penalty)
        self.weights = _normalize(w)
        self._append_outcome("incompatible", snap, notes)
        logger.info("Matching learning: adjusted weights after incompatible %s", self.weights)
        return self.get_weights()

    def _append_outcome(self, kind: str, snap: Dict[str, float], notes: Optional[str]) -> None:
        self.outcomes.append(
            {
                "kind": kind,
                "dimensions": snap,
                "notes": notes,
                "weights_after": copy.deepcopy(self.weights),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(self.outcomes) > 500:
            self.outcomes = self.outcomes[-500:]

    def recent_outcomes(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self.outcomes[-limit:]))
