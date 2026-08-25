"""
Test integrazione Decision Memory Activity Loop.

Verifica il collegamento:
WAITING_FOR_ACTIVITY
        ->
WAITING_FOR_OUTCOME
"""

from backend.decision_memory.activity_runtime import (
    DecisionMemoryActivityRuntime,
)
from backend.decision_memory.activity_processor import (
    DecisionMemoryActivityProcessor,
)
from backend.decision_memory.activity_matcher import (
    ActivityMatcher,
)
from backend.decision_memory.lifecycle import (
    DecisionEpisodeLifecycle,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


class FakeRepository:

    def __init__(
        self,
        episode,
    ):
        self.episode = episode
        self.updated = []

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
        decision_id="decision-123",
        status="WAITING_FOR_ACTIVITY",
        recommended_workout={
            "sport": "RUN",
            "duration_minutes": 60,
        },
    )


def test_activity_loop_moves_episode_to_waiting_for_outcome():
    episode = _episode()

    repository = FakeRepository(
        episode
    )

    processor = DecisionMemoryActivityProcessor(
        repository=repository,
        matcher=ActivityMatcher(),
        lifecycle=DecisionEpisodeLifecycle(),
    )

    runtime = DecisionMemoryActivityRuntime(
        repository=repository,
        processor_class=lambda repo: processor,
    )

    result = runtime.process_activities(
        athlete_id="athlete-123",
        activities=[
            {
                "source": "garmin",
                "source_id": "1001",
                "activity_id": "garmin:1001",
                "date": (
                    "2026-08-24T18:00:00Z"
                ),
                "sport": "RUN",
            },
        ],
    )

    assert result == [
        episode,
    ]

    assert episode.status == (
        "WAITING_FOR_OUTCOME"
    )

    assert episode.actual_activity_id == (
        "garmin:1001"
    )

    assert episode.actual_activity_source == (
        "garmin"
    )

    assert episode.actual_activity == {
        "source": "garmin",
        "source_id": "1001",
        "activity_id": "garmin:1001",
        "date": (
            "2026-08-24T18:00:00Z"
        ),
        "sport": "RUN",
    }

    assert repository.updated == [
        episode,
    ]