"""In-memory continuous learning store for traveler matching.

Purpose:
    Adjust multidimensional weights after successful connections or incompatibility reports.

Responsibilities:
    Normalize weights, record outcomes, cap history, and expose recent reads.

Dependencies:
    ``dataclasses``, ``datetime`` (UTC). Production should use persistence and batch training.

Note:
    Placeholder implementation (PBI 27); replace with a persistent store at scale.
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
    """Normalizes positive weights to sum 1 with rounding.

    Args:
        weights: Per-dimension weights.

    Returns:
        Normalized copy with four decimal places.
    """
    total = sum(max(v, 1e-6) for v in weights.values())
    return {k: round(v / total, 4) for k, v in weights.items()}


@dataclass
class MatchingLearningStore:
    """Holds feedback-derived weights for multidimensional scoring.

    Important attributes:
        weights: Mutable per-dimension weights (renormalized after each operation).
        outcomes: Bounded history of events with snapshot and resulting weights.
    """

    weights: Dict[str, float] = field(default_factory=lambda: copy.deepcopy(DEFAULT_WEIGHTS))
    outcomes: List[Dict[str, Any]] = field(default_factory=list)

    def get_weights(self) -> Dict[str, float]:
        """Returns current normalized weights.

        Returns:
            Dimension → relative weight map.
        """
        return _normalize(self.weights)

    def record_rating_feedback(self, rating: int) -> None:
        """Applies a small global nudge from star ratings (1–5).

        Args:
            rating: Integer typically between 1 and 5.
        """
        delta = (rating - 3) * 0.005
        for key in self.weights:
            self.weights[key] = max(MIN_WEIGHT, min(MAX_WEIGHT, self.weights[key] + delta * 0.2))
        self.weights = _normalize(self.weights)

    def record_success(
        self,
        dimension_snapshot: Optional[Dict[str, float]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, float]:
        """Reinforces dimensions that contributed to a successful connection.

        Args:
            dimension_snapshot: Per-dimension scores in [0, 1].
            notes: Optional free text for auditing.

        Returns:
            Normalized weights after reinforcement.
        """
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
        """Reduces weight of high dimensions that still led to incompatibility.

        Args:
            dimension_snapshot: Observed per-dimension scores.
            notes: Optional comment.

        Returns:
            Normalized weights after penalty.
        """
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
        """Appends a record to internal history and trims to the last 500.

        Args:
            kind: Outcome type (e.g. ``success`` or ``incompatible``).
            snap: Dimensional snapshot at event time.
            notes: Optional notes.
        """
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
        """Lists most recent outcomes in reverse storage order.

        Args:
            limit: Maximum number to return.

        Returns:
            List of dicts with metadata for each event.
        """
        return list(reversed(self.outcomes[-limit:]))
