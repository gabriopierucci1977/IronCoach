"""
IronCoach Activity Model

Modello interno comune per tutte le sorgenti:
- Garmin
- Strava
- manual entry
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class IronCoachActivity:
    """
    Rappresenta una singola attività reale
    dell'atleta nel sistema IronCoach.
    """

    # Identification
    activity_id: str
    source: str
    source_id: Optional[str] = None
    file_hash: Optional[str] = None

    # Timing
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Classification
    sport: Optional[str] = None
    activity_type: Optional[str] = None

    # General metrics
    duration_seconds: Optional[int] = None
    distance_meters: Optional[float] = None
    elevation_gain: Optional[float] = None
    calories: Optional[int] = None

    # Cardio
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None

    # Power
    avg_power: Optional[float] = None
    normalized_power: Optional[float] = None

    # Load
    training_load: Optional[float] = None

    # Complex structures
    laps: List[dict] = field(default_factory=list)
    segments: List[dict] = field(default_factory=list)

    # Source-specific additional data
    metadata: Dict = field(default_factory=dict)
