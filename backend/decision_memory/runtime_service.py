"""
IronCoach Decision Memory Runtime Service

Coordina il salvataggio iniziale di una decisione
nella Decision Memory.

Responsabilità:
- costruzione DecisionEpisode;
- persistenza iniziale;
- avanzamento lifecycle.

Non gestisce:
- matching attività;
- outcome;
- valutazione aderenza.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional

from backend.decision_memory.lifecycle import (
    DecisionEpisodeLifecycle,
)
from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


class DecisionMemoryRuntimeService:
    """
    Servizio runtime per la Decision Memory.
    """

    def __init__(
        self,
        runtime_config,
        repository_class=DecisionMemoryRepository,
        lifecycle_class=DecisionEpisodeLifecycle,
    ):
        database_path = getattr(
            runtime_config,
            "decision_memory_database_path",
            "data/ironcoach_memory.db",
        )

        self.repository = repository_class(
            database_path
        )

        self.lifecycle = lifecycle_class()

    def save_decision_memory(
        self,
        context,
        decision,
        airtable_record,
    ) -> Optional[DecisionEpisode]:
        episode = self._build_episode(
            context,
            decision,
            airtable_record,
        )

        if episode is None:
            return None

        self.repository.create(
            episode
        )

        self.lifecycle.mark_waiting_for_activity(
            episode
        )

        self.repository.update(
            episode
        )

        return episode

    def _build_episode(
        self,
        context,
        decision,
        airtable_record,
    ) -> Optional[DecisionEpisode]:
        identity = self._decision_memory_identity(
            context,
            decision,
        )

        if identity is None:
            return None

        airtable_record_id = None

        if isinstance(
            airtable_record,
            dict,
        ):
            airtable_record_id = (
                airtable_record.get(
                    "id"
                )
            )

        return DecisionEpisode(
            athlete_id=str(
                identity[
                    "athlete_id"
                ]
            ),
            decision_timestamp=self._utc_now(),
            decision_action=identity[
                "decision_action"
            ],
            rule_id=identity[
                "rule_id"
            ],
            primary_intent=identity[
                "primary_intent"
            ],
            pre_decision_state={
                "context": deepcopy(
                    context
                ),
            },
            athlete_state=deepcopy(
                identity[
                    "athlete"
                ]
            ),
            decision_id=identity[
                "decision_id"
            ],
            strategy=decision.get(
                "strategy"
            ),
            decision_confidence=decision.get(
                "confidence"
            ),
            supporting_intents=list(
                decision.get(
                    "supporting_intents",
                    [],
                )
                or []
            ),
            planned_workout=deepcopy(
                context.get(
                    "training"
                )
            ),
            recommended_workout=deepcopy(
                decision.get(
                    "modified_workout"
                )
            ),
            airtable_decision_record_id=(
                airtable_record_id
            ),
        )

    @staticmethod
    def _decision_memory_identity(
        context,
        decision,
    ):
        athlete = (
            context.get(
                "athlete",
                {},
            )
            or context.get(
                "athlete_profile",
                {},
            )
            or {}
        )

        athlete_id = athlete.get(
            "source_id"
        )

        decision_id = decision.get(
            "decision_id"
        )

        rule_id = decision.get(
            "rule_id"
        )

        primary_intent = decision.get(
            "primary_intent"
        )

        decision_action = decision.get(
            "decision"
        )

        if not all(
            (
                athlete_id,
                decision_id,
                rule_id,
                primary_intent,
                decision_action,
            )
        ):
            return None

        return {
            "athlete": athlete,
            "athlete_id": athlete_id,
            "decision_id": decision_id,
            "rule_id": rule_id,
            "primary_intent": primary_intent,
            "decision_action": decision_action,
        }

    @staticmethod
    def _utc_now() -> str:
        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )