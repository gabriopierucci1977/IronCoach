"""
Test Decision Memory Repository update.

Un DecisionEpisode già persistito deve poter avanzare
nel proprio ciclo di vita senza creare un nuovo episodio.
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
        supporting_intents=[
            "REDUCE_LOAD",
        ],
        pre_decision_state={},
        athlete_state={},
    )


def test_repository_updates_existing_decision_episode(
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

    episode.status = "WAITING_FOR_OUTCOME"

    episode.actual_activity_id = "garmin-789"
    episode.actual_activity_source = "GARMIN"

    episode.adherence_status = "FOLLOWED"
    episode.adherence_evidence = {
        "sport": "matched",
        "duration": "matched",
    }
    episode.adherence_evaluated_at = (
        "2026-08-24T12:00:00Z"
    )

    repository.update(
        episode
    )

    loaded = repository.get_by_episode_id(
        episode.episode_id
    )

    assert loaded is not None

    assert loaded.status == "WAITING_FOR_OUTCOME"

    assert loaded.actual_activity_id == "garmin-789"
    assert loaded.actual_activity_source == "GARMIN"

    assert loaded.adherence_status == "FOLLOWED"

    assert loaded.adherence_evidence == {
        "sport": "matched",
        "duration": "matched",
    }

    assert (
        loaded.adherence_evaluated_at
        == "2026-08-24T12:00:00Z"
    )