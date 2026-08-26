"""
Test Decision Memory Activity Runtime.

Collega attività reali agli episodi
WAITING_FOR_ACTIVITY.
"""

from types import SimpleNamespace

from backend.decision_memory.activity_runtime import (
    DecisionMemoryActivityRuntime,
)


class FakeRepository:

    def __init__(self):
        self.updated = []

        self.episode = SimpleNamespace(
            episode_id="episode-1",
            status="WAITING_FOR_ACTIVITY",
        )

    def list_pending_by_athlete(
        self,
        athlete_id,
    ):
        return [
            self.episode,
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
        activities,
    ):
        self.calls.append(
            (
                episode,
                activities,
            )
        )

        return episode


def test_activity_runtime_processes_pending_episodes():
    repository = FakeRepository()

    runtime = DecisionMemoryActivityRuntime(
        repository=repository,
        processor_class=FakeProcessor,
    )

    result = runtime.process_activities(
        athlete_id="athlete-123",
        activities=[
            {
                "activity_id": "garmin:1001",
            },
        ],
    )

    assert result == [
        repository.episode,
    ]
