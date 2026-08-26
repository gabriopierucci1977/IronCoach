"""
Test OutcomeEvaluator Decision Memory.
"""

from backend.decision_memory.outcome_evaluator import (
    OutcomeEvaluator,
)
from backend.models.decision_episode import (
    DecisionEpisode,
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
        status="WAITING_FOR_OUTCOME",
        planned_workout={
            "sport": "RUN",
            "duration_minutes": 60,
        },
        actual_activity={
            "sport": "RUN",
            "duration_minutes": 55,
        },
    )


def test_outcome_evaluator_marks_matching_activity():
    result = OutcomeEvaluator().evaluate(
        _episode()
    )

    assert result["adherence_status"] == (
        "FOLLOWED"
    )


def test_outcome_evaluator_marks_wrong_sport():
    episode = _episode()

    episode.actual_activity = {
        "sport": "BIKE",
        "duration_minutes": 55,
    }

    result = OutcomeEvaluator().evaluate(
        episode
    )

    assert result["adherence_status"] == (
        "NOT_FOLLOWED"
    )


def test_outcome_evaluator_does_not_treat_missing_data_as_failure():
    episode = _episode()
    episode.planned_workout = {}

    result = OutcomeEvaluator().evaluate(
        episode
    )

    assert result["adherence_status"] == (
        "UNKNOWN"
    )
