"""
Test Decision Memory Repository latest.
"""

from backend.decision_memory.repository import (
    DecisionMemoryRepository,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def _episode(
    episode_id,
    timestamp,
):
    return DecisionEpisode(
        athlete_id="athlete-1",
        decision_timestamp=timestamp,
        decision_action="ADATTA",
        rule_id="RULE-1",
        primary_intent="REDUCE_LOAD",
        pre_decision_state={},
        athlete_state={},
        episode_id=episode_id,
    )


def test_repository_returns_latest_episodes(
    tmp_path,
):

    repository = DecisionMemoryRepository(
        tmp_path / "memory.db"
    )

    repository.create(
        _episode(
            "episode-old",
            "2026-08-20T08:00:00Z",
        )
    )

    repository.create(
        _episode(
            "episode-new",
            "2026-08-25T08:00:00Z",
        )
    )

    episodes = repository.latest(
        limit=1,
    )

    assert len(
        episodes
    ) == 1

    assert episodes[0].episode_id == (
        "episode-new"
    )