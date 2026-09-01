from types import SimpleNamespace

from backend.decision_memory.injury_outcome_processor import (
    DecisionMemoryInjuryOutcomeProcessor,
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
    return SimpleNamespace(
        episode_id="episode-injury",
        status="WAITING_FOR_OUTCOME",
        decision_timestamp="2026-08-24T09:00:00Z",
        primary_intent="PROTECT_INJURY",
        pre_decision_state={
            "training": {
                "date": "2026-08-24",
                "pain_score": 6,
                "current_problem": None,
            },
        },
    )


def test_protect_injury_uses_current_signal_trend():
    repository = FakeRepository()

    processor = DecisionMemoryInjuryOutcomeProcessor(
        repository=repository,
    )

    episode = _episode()

    result = processor.process(
        episode=episode,
        training_history=[
            {
                "date": "2026-08-25",
                "pain_score": 2,
            },
            {
                "date": "2026-08-27",
                "pain_score": 6,
            },
            {
                "date": "2026-08-30",
                "pain_score": 8,
                "current_problem": (
                    "dolore acuto"
                ),
            },
        ],
        as_of="2026-08-31T09:00:00Z",
    )

    assert result.outcome_24h_status == "POSITIVE"
    assert result.outcome_72h_status == "NEUTRAL"
    assert result.outcome_7d_status == "NEGATIVE"
    assert result.overall_outcome_status == "NEGATIVE"
    assert result.outcome_evaluator_version == "injury-outcome-v1"
    assert result.status == "COMPLETE"


def test_protect_injury_missing_signal_is_insufficient():
    repository = FakeRepository()

    processor = DecisionMemoryInjuryOutcomeProcessor(
        repository=repository,
    )

    episode = _episode()

    result = processor.process(
        episode=episode,
        training_history=[
            {
                "date": "2026-08-25",
                "sport": "RUN",
            },
            {
                "date": "2026-08-27",
                "sport": "BIKE",
            },
            {
                "date": "2026-08-30",
                "sport": "SWIM",
            },
        ],
        as_of="2026-08-31T09:00:00Z",
    )

    assert (
        result.outcome_24h_status
        == "INSUFFICIENT_DATA"
    )
    assert (
        result.outcome_72h_status
        == "INSUFFICIENT_DATA"
    )
    assert (
        result.outcome_7d_status
        == "INSUFFICIENT_DATA"
    )
    assert (
        result.overall_outcome_status
        == "INSUFFICIENT_DATA"
    )
    assert result.status == "COMPLETE"
