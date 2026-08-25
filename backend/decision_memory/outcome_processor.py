"""
IronCoach Decision Memory Outcome Processor

Coordina la valutazione dell'outcome
e l'aggiornamento del DecisionEpisode.

Non decide la logica di valutazione:
delega a OutcomeEvaluator.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.decision_memory.outcome_evaluator import (
    OutcomeEvaluator,
)


class DecisionMemoryOutcomeProcessor:
    """
    Processa outcome su episodi completati.
    """

    def __init__(
        self,
        repository,
        evaluator=None,
    ):
        self.repository = repository
        self.evaluator = (
            evaluator
            or OutcomeEvaluator()
        )

    def process(
        self,
        episode,
    ):
        result = self.evaluator.evaluate(
            episode
        )

        episode.adherence_status = (
            result[
                "adherence_status"
            ]
        )

        episode.adherence_evidence = (
            result[
                "evidence"
            ]
        )

        episode.adherence_evaluated_at = (
            self._utc_now()
        )

        self.repository.update(
            episode
        )

        return episode

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