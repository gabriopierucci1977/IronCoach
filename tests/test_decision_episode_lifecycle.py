"""
Test ciclo di vita DecisionEpisode.

Il lifecycle gestisce le transizioni di stato
senza occuparsi di persistenza, matching attività
o valutazione degli outcome.
"""

import pytest

from backend.decision_memory.lifecycle import (
    DecisionEpisodeLifecycle,
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


def test_open_episode_moves_to_waiting_for_activity():
    episode = _episode()

    lifecycle = DecisionEpisodeLifecycle()

    result = lifecycle.mark_waiting_for_activity(
        episode
    )

    assert result is episode
    assert episode.status == "WAITING_FOR_ACTIVITY"


def test_waiting_for_activity_requires_open_episode():
    episode = _episode()
    episode.status = "WAITING_FOR_OUTCOME"

    lifecycle = DecisionEpisodeLifecycle()

    with pytest.raises(
        ValueError,
        match="OPEN",
    ):
        lifecycle.mark_waiting_for_activity(
            episode
        )

    assert episode.status == "WAITING_FOR_OUTCOME"