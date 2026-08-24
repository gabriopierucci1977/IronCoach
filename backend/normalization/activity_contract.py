"""Canonical normalized activity contract used by IronCoach.

The normalization layer is the boundary between external schemas (Airtable,
Garmin, Strava/manual input) and the coaching pipeline.  Analyzer code should
prefer these canonical keys and use ``raw`` only as a backwards-compatible
fallback.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict


class NormalizedActivity(TypedDict):
    """Stable dictionary contract returned by :class:`ActivityNormalizer`."""

    source: str
    source_id: Any
    date: Any
    sport: str
    workout_name: Any
    session_type: Any
    duration_minutes: Optional[float]
    distance_km: float
    training_load: Any
    intensity: Any
    heart_rate: Dict[str, Any]
    power: Dict[str, Any]
    rpe: Any
    notes: Any
    current_problem: Any
    pain_score: Any
    raw: Dict[str, Any]
