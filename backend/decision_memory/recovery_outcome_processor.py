"""
IronCoach Decision Memory Recovery Outcome Processor.

Applica al DecisionEpisode gli outcome recovery
calcolati nelle finestre 24h, 72h e 7d.

Principi:
- aderenza e outcome restano concetti separati;
- le finestre non ancora mature restano senza status;
- l'overall viene definito solo alla maturazione dei 7 giorni;
- l'overall usa il 7d salvo un risultato intent-specific fornito dall'evaluator;
- dati insufficienti a 7d producono un outcome INSUFFICIENT_DATA ma chiudono l'episodio COMPLETE.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.decision_memory.recovery_outcome_evaluator import (
    DecisionMemoryRecoveryOutcomeEvaluator,
)


class DecisionMemoryRecoveryOutcomeProcessor:
    """
    Persiste gli outcome recovery di un DecisionEpisode.
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
            else DecisionMemoryRecoveryOutcomeEvaluator()
        )

    def process(
        self,
        episode,
        recovery_history,
        as_of=None,
    ):
        if episode.status != "WAITING_FOR_OUTCOME":
            return episode

        evaluation = self.evaluator.evaluate(
            episode=episode,
            recovery_history=recovery_history,
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

        intent_specific_overall = (
            evaluation.get(
                "overall"
            )
        )

        overall = (
            intent_specific_overall
            if intent_specific_overall is not None
            else outcome_7d
        )

        overall_status = overall.get(
            "status"
        )

        if (
            outcome_7d_status is not None
            and overall_status is not None
        ):
            episode.overall_outcome_status = (
                overall_status
            )

            episode.overall_outcome_evidence = {
                "source_window": (
                    "overall"
                    if intent_specific_overall
                    is not None
                    else "7d"
                ),
                "window_evidence": (
                    overall.get(
                        "evidence",
                        {},
                    )
                ),
            }

            episode.overall_outcome_evaluated_at = (
                evaluated_at
            )

            episode.outcome_evaluator_version = (
                "recovery-outcome-v2"
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
