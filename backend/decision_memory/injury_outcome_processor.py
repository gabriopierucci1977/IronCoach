"""
IronCoach Decision Memory Injury Outcome Processor.

Applica al DecisionEpisode gli outcome injury
calcolati nelle finestre 24h, 72h e 7d.

L'overall coincide con il risultato della finestra 7d.
INSUFFICIENT_DATA a 7d è un outcome finale valido e
chiude l'episodio come COMPLETE.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.decision_memory.injury_outcome_evaluator import (
    DecisionMemoryInjuryOutcomeEvaluator,
)


class DecisionMemoryInjuryOutcomeProcessor:
    """
    Persiste gli outcome PROTECT_INJURY.
    """

    def __init__(
        self,
        repository,
        evaluator=None,
    ):
        self.repository = repository

        self.evaluator = (
            evaluator
            if evaluator is not None
            else DecisionMemoryInjuryOutcomeEvaluator()
        )

    def process(
        self,
        episode,
        training_history,
        as_of=None,
    ):
        if episode.status != "WAITING_FOR_OUTCOME":
            return episode

        evaluation = self.evaluator.evaluate(
            episode=episode,
            training_history=training_history,
            as_of=as_of,
        )

        evaluated_at = self._utc_now()

        self._apply_window(
            episode=episode,
            evaluation=evaluation.get(
                "24h",
                {},
            ),
            status_field="outcome_24h_status",
            evidence_field="outcome_24h_evidence",
            evaluated_at_field=(
                "outcome_24h_evaluated_at"
            ),
            evaluated_at=evaluated_at,
        )

        self._apply_window(
            episode=episode,
            evaluation=evaluation.get(
                "72h",
                {},
            ),
            status_field="outcome_72h_status",
            evidence_field="outcome_72h_evidence",
            evaluated_at_field=(
                "outcome_72h_evaluated_at"
            ),
            evaluated_at=evaluated_at,
        )

        self._apply_window(
            episode=episode,
            evaluation=evaluation.get(
                "7d",
                {},
            ),
            status_field="outcome_7d_status",
            evidence_field="outcome_7d_evidence",
            evaluated_at_field=(
                "outcome_7d_evaluated_at"
            ),
            evaluated_at=evaluated_at,
        )

        outcome_7d = evaluation.get(
            "7d",
            {},
        )

        outcome_7d_status = outcome_7d.get(
            "status"
        )

        if outcome_7d_status is not None:
            episode.overall_outcome_status = (
                outcome_7d_status
            )

            episode.overall_outcome_evidence = {
                "source_window": "7d",
                "window_evidence": (
                    outcome_7d.get(
                        "evidence",
                        {},
                    )
                ),
            }

            episode.overall_outcome_evaluated_at = (
                evaluated_at
            )

            episode.outcome_evaluator_version = (
                "injury-outcome-v1"
            )

            episode.status = "COMPLETE"

        self.repository.update(
            episode
        )

        return episode

    @staticmethod
    def _apply_window(
        episode,
        evaluation,
        status_field,
        evidence_field,
        evaluated_at_field,
        evaluated_at,
    ):
        status = evaluation.get(
            "status"
        )

        if status is None:
            return

        setattr(
            episode,
            status_field,
            status,
        )

        setattr(
            episode,
            evidence_field,
            evaluation.get(
                "evidence",
                {},
            ),
        )

        setattr(
            episode,
            evaluated_at_field,
            evaluated_at,
        )

    @staticmethod
    def _utc_now():
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
