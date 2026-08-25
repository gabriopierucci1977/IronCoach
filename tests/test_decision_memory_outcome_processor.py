"""
Test Decision Memory Outcome Processor.
"""

from backend.decision_memory.outcome_processor import (
    DecisionMemoryOutcomeProcessor,
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


def _episode():
    return DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp=(
            "2026-08-24T09:00:00Z"
        ),
        decision_action="ADATTA",
        rule_id=(
            "PERFORMANCE_DECLINING_LOAD_HIGH"
        ),
        primary_intent=(
            "PROTECT_PERFORMANCE"
        ),
        pre_decision_state={},
        athlete_state={},
        status="WAITING_FOR_OUTCOME",
        planned_workout={
            "sport": "RUN",
            "duration_minutes": 60,
        },
        actual_activity={
            "sport": "RUN",
            "duration_minutes": 55,
        },
    )


def test_processor_updates_episode_with_outcome():
    repository = FakeRepository()

    processor = DecisionMemoryOutcomeProcessor(
        repository=repository,
    )

    result = processor.process(
        _episode()
    )

    assert result.adherence_status == (
        "MATCHED"
    )

    assert result.adherence_evidence == {
        "planned_sport": "RUN",
        "actual_sport": "RUN",
        "planned_duration_minutes": 60,
        "actual_duration_minutes": 55,
    }

    assert repository.updated == [
        result,
    ]