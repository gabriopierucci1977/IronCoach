"""
Regression test per il contratto finale degli outcome recovery.

INSUFFICIENT_DATA rappresenta un outcome valutato con dati
insufficienti e non un errore tecnico: a 7d l'episodio deve
quindi diventare COMPLETE.
"""

from backend.decision_memory.recovery_outcome_processor import (
    DecisionMemoryRecoveryOutcomeProcessor,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


class FakeRepository:

    def __init__(self):
        self.updated = []

    def update(
        self,
        episode,
    ):
        self.updated.append(
            episode
        )


class FakeEvaluator:

    def evaluate(
        self,
        episode,
        recovery_history,
        as_of=None,
    ):
        return {
            "24h": {
                "status": "INSUFFICIENT_DATA",
                "evidence": {
                    "reason": "missing_data",
                },
            },
            "72h": {
                "status": "INSUFFICIENT_DATA",
                "evidence": {
                    "reason": "missing_data",
                },
            },
            "7d": {
                "status": "INSUFFICIENT_DATA",
                "evidence": {
                    "reason": "missing_data",
                },
            },
        }


def test_insufficient_data_at_7d_completes_episode():
    repository = FakeRepository()

    processor = DecisionMemoryRecoveryOutcomeProcessor(
        repository=repository,
        evaluator=FakeEvaluator(),
    )

    episode = DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="ADATTA",
        rule_id="RECOVERY_UNKNOWN",
        primary_intent="MANAGE_UNCERTAINTY",
        pre_decision_state={},
        athlete_state={},
        status="WAITING_FOR_OUTCOME",
    )

    result = processor.process(
        episode=episode,
        recovery_history=[],
        as_of="2026-09-01T09:00:00Z",
    )

    assert result.status == "COMPLETE"
    assert result.outcome_7d_status == "INSUFFICIENT_DATA"
    assert result.overall_outcome_status == "INSUFFICIENT_DATA"
    assert repository.updated == [
        episode,
    ]

def test_manage_uncertainty_keeps_early_recovery_success_in_overall():
    repository = FakeRepository()

    processor = DecisionMemoryRecoveryOutcomeProcessor(
        repository=repository,
    )

    episode = DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="ADATTA",
        rule_id="RECOVERY_UNKNOWN",
        primary_intent="MANAGE_UNCERTAINTY",
        pre_decision_state={
            "recovery": {},
        },
        athlete_state={},
        status="WAITING_FOR_OUTCOME",
    )

    result = processor.process(
        episode=episode,
        recovery_history=[
            {
                "date": "2026-08-25",
                "readiness": 82,
                "sleep": {
                    "score": 78,
                },
            },
        ],
        as_of="2026-08-31T09:00:00Z",
    )

    assert result.outcome_24h_status == "POSITIVE"
    assert result.outcome_72h_status == "INSUFFICIENT_DATA"
    assert result.outcome_7d_status == "INSUFFICIENT_DATA"
    assert result.overall_outcome_status == "POSITIVE"
    assert result.status == "COMPLETE"
