"""
IronCoach Activity Segment Model

Rappresenta una singola parte di una attività:
- swim
- bike
- run
- transition
- strength
"""

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class IronCoachActivitySegment:
    """
    Segmento interno di una attività IronCoach.
    """

    # Classification

    sport: Optional[str] = None

    activity_type: Optional[str] = None


    # Timing

    start_time: Optional[str] = None

    duration_seconds: Optional[int] = None


    # Distance / movement

    distance_meters: Optional[float] = None

    elevation_gain: Optional[float] = None

    elevation_loss: Optional[float] = None


    # Cardio

    avg_hr: Optional[int] = None

    max_hr: Optional[int] = None


    # Performance metrics

    avg_speed: Optional[float] = None

    max_speed: Optional[float] = None

    avg_power: Optional[float] = None

    normalized_power: Optional[float] = None

    avg_cadence: Optional[float] = None

    max_cadence: Optional[float] = None


    # Training metrics

    training_load: Optional[float] = None

    training_effect: Optional[float] = None


    # Additional Garmin/Strava data

    metadata: Dict = field(
        default_factory=dict
    )