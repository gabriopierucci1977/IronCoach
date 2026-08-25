"""
Test Decision Memory Runtime Service.

Coordina creazione e avanzamento iniziale
del DecisionEpisode.
"""

from backend.decision_memory.runtime_service import (
    DecisionMemoryRuntimeService,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


class FakeRepository:
    def __init__(
        self,
        database_path,
    ):
        self.database_path = database_path
        self.created = []
        self.updated = []

    def create(
        self,
        episode,
    ):
        self.created.append(
            episode
        )

    def update(
        self,
        episode,
    ):
        self.updated.append(
            episode
        )


class FakeLifecycle:
    def mark_waiting_for_activity(
        self,
        episode,
    ):
        episode.status = "WAITING_FOR_ACTIVITY"
        return episode


class FakeRuntimeConfig:
    decision_memory_database_path = (
        "data/test_ironcoach_memory.db"
    )


def test_runtime_service_creates_and_advances_episode():
    service = DecisionMemoryRuntimeService(
        runtime_config=FakeRuntimeConfig(),
        repository_class=FakeRepository,
        lifecycle_class=FakeLifecycle,
    )

    episode = service.save_decision_memory(
        context={
            "athlete": {
                "source_id": "recAthlete123",
                "identity": {
                    "name": "Gabrio",
                },
            },
            "training": {
                "sport": "RUN",
                "duration_minutes": 60,
            },
        },
        decision={
            "decision": "ADATTA",
            "decision_id": (
                "123e4567-e89b-42d3-a456-426614174000"
            ),
            "rule_id": (
                "PERFORMANCE_DECLINING_LOAD_HIGH"
            ),
            "primary_intent": (
                "PROTECT_PERFORMANCE"
            ),
            "strategy": "ADAPT",
            "confidence": 88,
            "supporting_intents": [
                "REDUCE_LOAD",
            ],
            "modified_workout": {
                "sport": "RUN",
                "duration_minutes": 40,
            },
        },
        airtable_record={
            "id": "recDecision789",
        },
    )

    assert isinstance(
        episode,
        DecisionEpisode,
    )

    assert episode.athlete_id == (
        "recAthlete123"
    )

    assert episode.status == (
        "WAITING_FOR_ACTIVITY"
    )