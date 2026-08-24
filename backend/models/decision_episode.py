"""
IronCoach DecisionEpisode Model

Rappresenta il ciclo di vita completo di una decisione
IronCoach all'interno della Decision Memory.

Il modello conserva:
- identità dell'episodio e della decisione;
- stato pre-decisione;
- metadati decisionali;
- attività realmente eseguita;
- aderenza;
- outcome temporali;
- audit e versioni degli evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _uuid4_string() -> str:
    return str(
        uuid4()
    )


@dataclass
class DecisionEpisode:

    athlete_id: str
    decision_timestamp: str
    decision_action: str
    rule_id: str
    primary_intent: str
    pre_decision_state: Dict[str, Any]
    athlete_state: Dict[str, Any]

    episode_id: str = field(
        default_factory=_uuid4_string
    )

    decision_id: Optional[str] = None

    status: str = "OPEN"

    schema_version: str = "1"

    strategy: Optional[str] = None

    decision_confidence: Optional[int] = None

    supporting_intents: List[str] = field(
        default_factory=list
    )

    planned_workout: Optional[Dict[str, Any]] = None

    recommended_workout: Optional[Dict[str, Any]] = None

    actual_activity: Optional[Dict[str, Any]] = None

    actual_activity_id: Optional[str] = None

    actual_activity_source: Optional[str] = None

    adherence_status: Optional[str] = None

    adherence_evidence: Dict[str, Any] = field(
        default_factory=dict
    )

    adherence_evaluated_at: Optional[str] = None

    outcome_24h_status: Optional[str] = None

    outcome_24h_evidence: Dict[str, Any] = field(
        default_factory=dict
    )

    outcome_24h_evaluated_at: Optional[str] = None

    outcome_72h_status: Optional[str] = None

    outcome_72h_evidence: Dict[str, Any] = field(
        default_factory=dict
    )

    outcome_72h_evaluated_at: Optional[str] = None

    outcome_7d_status: Optional[str] = None

    outcome_7d_evidence: Dict[str, Any] = field(
        default_factory=dict
    )

    outcome_7d_evaluated_at: Optional[str] = None

    overall_outcome_status: Optional[str] = None

    overall_outcome_confidence: Optional[int] = None

    overall_outcome_evidence: Dict[str, Any] = field(
        default_factory=dict
    )

    overall_outcome_evaluated_at: Optional[str] = None

    decision_engine_version: Optional[str] = None

    adherence_evaluator_version: Optional[str] = None

    outcome_evaluator_version: Optional[str] = None

    airtable_decision_record_id: Optional[str] = None

    created_at: str = field(
        default_factory=_utc_now
    )

    updated_at: str = field(
        default_factory=_utc_now
    )