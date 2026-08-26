"""
Test Decision Memory Repository evaluated history.
"""

from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def _episode(
    episode_id,
    athlete_id,
    timestamp,
    outcome=None,
):
    return DecisionEpisode(
        athlete_id=athlete_id,
        decision_timestamp=timestamp,
        decision_action="ADATTA",
        rule_id="PERFORMANCE_DECLINING_LOAD_HIGH",
        primary_intent="PROTECT_PERFORMANCE",
        pre_decision_state={},
        athlete_state={},
        episode_id=episode_id,
        overall_outcome_status=outcome,
    )


def test_repository_returns_only_evaluated_episodes_for_athlete(
    tmp_path,
):
    repository = DecisionMemoryRepository(
        tmp_path / "memory.db"
    )

    repository.create(
        _episode(
            "episode-positive",
            "athlete-1",
            "2026-08-20T08:00:00Z",
            "POSITIVE",
        )
    )

    repository.create(
        _episode(
            "episode-insufficient",
            "athlete-1",
            "2026-08-21T08:00:00Z",
            "INSUFFICIENT_DATA",
        )
    )

    repository.create(
        _episode(
            "episode-pending",
            "athlete-1",
            "2026-08-22T08:00:00Z",
        )
    )

    repository.create(
        _episode(
            "episode-other-athlete",
            "athlete-2",
            "2026-08-23T08:00:00Z",
            "NEGATIVE",
        )
    )

    episodes = (
        repository.list_evaluated_by_athlete(
            "athlete-1"
        )
    )

    episode_ids = {
        episode.episode_id
        for episode in episodes
    }

    assert episode_ids == {
        "episode-positive",
        "episode-insufficient",
    }
