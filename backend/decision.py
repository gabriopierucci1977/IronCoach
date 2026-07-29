"""
IronCoach Decision Model

Definisce la struttura ufficiale di una decisione
presa dal Coach Engine.
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Decision:

    decision: str
    reason: str

    priority: str = "Recovery"

    confidence: int = 100

    strategy: str = ""

    recommended_action: str = ""

    modified_workout: Optional[dict] = None

    def to_dict(self):

        return asdict(self)