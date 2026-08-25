"""
Test activity recording updates decision memory.
"""

from backend.decision_memory.activity_runtime import (
    DecisionMemoryActivityRuntime,
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


class FakeProcessor:

    def process(
        self,
        episode,
        activities,
    ):
        episode.actual_activity = (
            activities[0]
        )
        episode.status = (
            "WAITING_FOR_OUTCOME"
        )

        return episode


def test_activity_runtime_updates_episode():

    repository = FakeRepository()

    runtime = DecisionMemoryActivityRuntime(
        repository=repository,
        processor=FakeProcessor(),
    )

    result = runtime.record_activity(
        {
            "sport": "RUN",
            "duration_minutes": 45,
            "completed": True,
        }
    )

    assert result.status == (
        "WAITING_FOR_OUTCOME"
    )

    assert result.actual_activity[
        "sport"
    ] == "RUN"