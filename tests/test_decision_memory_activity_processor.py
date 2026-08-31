"""
Test Decision Memory Activity Processor.

Coordina:
- ricerca attività;
- transizione lifecycle;
- aggiornamento repository.
"""

from backend.decision_memory.activity_processor import (
    DecisionMemoryActivityProcessor,
)
from backend.models.decision_episode import (
    DecisionEpisode,
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


def _episode():
    return DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="ADATTA",
        rule_id="PERFORMANCE_DECLINING_LOAD_HIGH",
        primary_intent="PROTECT_PERFORMANCE",
        pre_decision_state={},
        athlete_state={},
        status="WAITING_FOR_ACTIVITY",
        recommended_workout={
            "sport": "RUN",
        },
    )


def test_processor_links_activity_and_updates_repository():
    repository = FakeRepository()

    processor = DecisionMemoryActivityProcessor(
        repository
    )

    processor.process(
        _episode(),
        [
            {
                "source": "garmin",
                "source_id": "1001",
                "activity_id": "garmin:1001",
                "date": "2026-08-24T18:00:00Z",
                "sport": "RUN",
            },
        ],
    )

    episode = repository.updated[0]

    assert episode.status == "WAITING_FOR_OUTCOME"

    assert episode.actual_activity_id == (
        "garmin:1001"
    )

def test_processor_advances_ambiguous_match_without_guessing():
    repository = FakeRepository()

    processor = DecisionMemoryActivityProcessor(
        repository
    )

    episode = _episode()

    result = processor.process(
        episode,
        [
            {
                "source": "garmin",
                "source_id": "2001",
                "activity_id": "garmin:2001",
                "date": "2026-08-24T18:00:00Z",
                "sport": "RUN",
            },
            {
                "source": "garmin",
                "source_id": "2002",
                "activity_id": "garmin:2002",
                "date": "2026-08-25T18:00:00Z",
                "sport": "RUN",
            },
        ],
    )

    assert result is episode
    assert episode.status == "WAITING_FOR_OUTCOME"
    assert episode.actual_activity is None
    assert episode.actual_activity_id is None
    assert episode.actual_activity_source is None
    assert repository.updated == [
        episode,
    ]
