"""
IronCoach Decision Memory Orchestrator

Coordina il ciclo completo della Decision Memory.

Responsabilità:
- delegare salvataggio decisione;
- delegare collegamento attività;
- delegare valutazione outcome.

Non contiene:
- logica di matching;
- logica valutativa;
- regole coaching.
"""

from __future__ import annotations


class DecisionMemoryOrchestrator:
    """
    Punto di ingresso unico per il ciclo Decision Memory.
    """

    def __init__(
        self,
        decision_runtime,
        activity_runtime,
        outcome_runtime,
        learning_service=None,
    ):
        self.decision_runtime = (
            decision_runtime
        )

        self.activity_runtime = (
            activity_runtime
        )

        self.outcome_runtime = (
            outcome_runtime
        )

        self.learning_service = (
            learning_service
        )

    def build_learning_evidence(
        self,
        athlete_id,
    ):
        if self.learning_service is None:
            return {}

        return (
            self.learning_service
            .build_evidence(
                athlete_id
            )
        )

    def save_decision(
        self,
        context,
        decision,
        airtable_record,
    ):
        return (
            self.decision_runtime
            .save_decision_memory(
                context,
                decision,
                airtable_record,
            )
        )

    def process_activity(
        self,
        athlete_id,
        activities,
    ):
        return (
            self.activity_runtime
            .process_activities(
                athlete_id,
                activities,
            )
        )

    def process_outcome(
        self,
        athlete_id,
        recovery_history=None,
        as_of=None,
    ):
        return (
            self.outcome_runtime
            .process_outcomes(
                athlete_id,
                recovery_history=(
                    recovery_history
                ),
                as_of=as_of,
            )
        )
