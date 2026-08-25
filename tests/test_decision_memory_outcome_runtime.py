"""
Test Decision Memory Outcome Runtime.

Processa episodi in attesa di outcome.
"""

from backend.decision_memory.outcome_runtime import (
    DecisionMemoryOutcomeRuntime,
)


class FakeRepository:

    def __init__(self):
        self.updated = []

    def list_pending_outcomes(
        self,
        athlete_id,
    ):
        return [
            "episode-1",
        ]

    def update(
        self,
        episode,
    ):
        self.updated.append(
            episode
        )


class FakeProcessor:

    def __init__(
        self,
        repository,
    ):
        self.repository = repository
        self.calls = []

    def process(
        self,
        episode,
    ):
        self.calls.append(
            episode
        )
        return episode


def test_outcome_runtime_processes_pending_episodes():
    repository = FakeRepository()

    runtime = DecisionMemoryOutcomeRuntime(
        repository=repository,
        processor_class=FakeProcessor,
    )

    result = runtime.process_outcomes(
        athlete_id="athlete-123",
    )

    assert result == [
        "episode-1",
    ]