"""
Test Decision Memory Repository.

Il repository persiste DecisionEpisode in SQLite
e ricostruisce il modello senza perdere informazioni.
"""

from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def _episode():
    return DecisionEpisode(
        athlete_id="athlete-123",
        decision_id="decision-456",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="ADATTA",
        strategy="ADAPT",
        rule_id="PERFORMANCE_DECLINING_LOAD_HIGH",
        primary_intent="PROTECT_PERFORMANCE",
        decision_confidence=89,
        supporting_intents=[
            "REDUCE_LOAD",
        ],
        pre_decision_state={
            "recovery": {
                "level": "LOW",
            },
            "load": {
                "level": "HIGH",
            },
        },
        athlete_state={
            "goal_type": "PERFORMANCE",
        },
        planned_workout={
            "sport": "RUN",
            "duration_minutes": 60,
        },
        recommended_workout={
            "sport": "RUN",
            "duration_minutes": 45,
        },
    )


def test_repository_creates_and_reads_decision_episode(
    tmp_path,
):
    database_path = (
        tmp_path
        / "ironcoach_memory.db"
    )

    repository = DecisionMemoryRepository(
        database_path
    )

    episode = _episode()

    repository.create(
        episode
    )

    loaded = repository.get_by_episode_id(
        episode.episode_id
    )

    assert loaded is not None

    assert loaded.episode_id == episode.episode_id
    assert loaded.decision_id == "decision-456"
    assert loaded.athlete_id == "athlete-123"

    assert loaded.decision_action == "ADATTA"
    assert loaded.strategy == "ADAPT"

    assert (
        loaded.rule_id
        == "PERFORMANCE_DECLINING_LOAD_HIGH"
    )

    assert (
        loaded.primary_intent
        == "PROTECT_PERFORMANCE"
    )

    assert loaded.supporting_intents == [
        "REDUCE_LOAD",
    ]

    assert loaded.pre_decision_state == {
        "recovery": {
            "level": "LOW",
        },
        "load": {
            "level": "HIGH",
        },
    }

    assert loaded.athlete_state == {
        "goal_type": "PERFORMANCE",
    }

    assert loaded.planned_workout == {
        "sport": "RUN",
        "duration_minutes": 60,
    }

    assert loaded.recommended_workout == {
        "sport": "RUN",
        "duration_minutes": 45,
    }