"""
Test ActivityMatcher Decision Memory.

Collega una decisione ad una attività realmente svolta.
"""

from backend.decision_memory.activity_matcher import (
    ActivityMatcher,
)
from backend.models.decision_episode import (
    DecisionEpisode,
)


def _episode(
    *,
    recommended_workout=None,
    planned_workout=None,
):
    return DecisionEpisode(
        athlete_id="athlete-123",
        decision_timestamp="2026-08-24T09:00:00Z",
        decision_action="ADATTA",
        rule_id="PERFORMANCE_DECLINING_LOAD_HIGH",
        primary_intent="PROTECT_PERFORMANCE",
        pre_decision_state={},
        athlete_state={},
        recommended_workout=(
            recommended_workout
            if recommended_workout is not None
            else {
                "sport": "RUN",
            }
        ),
        planned_workout=planned_workout,
    )


def test_matcher_returns_activity_after_decision():
    matcher = ActivityMatcher()

    activity = matcher.find_match(
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

    assert activity["source_id"] == "1001"


def test_matcher_ignores_activity_before_decision():
    matcher = ActivityMatcher()

    activity = matcher.find_match(
        _episode(),
        [
            {
                "source": "garmin",
                "source_id": "1000",
                "activity_id": "garmin:1000",
                "date": "2026-08-23T18:00:00Z",
                "sport": "RUN",
            },
        ],
    )

    assert activity is None


def test_matcher_does_not_guess_between_multiple_compatible_activities():
    matcher = ActivityMatcher()

    activity = matcher.find_match(
        _episode(),
        [
            {
                "source": "garmin",
                "source_id": "1001",
                "activity_id": "garmin:1001",
                "date": "2026-08-24T18:00:00Z",
                "sport": "RUN",
            },
            {
                "source": "garmin",
                "source_id": "1002",
                "activity_id": "garmin:1002",
                "date": "2026-08-25T08:00:00Z",
                "sport": "RUN",
            },
        ],
    )

    assert activity is None


def test_matcher_uses_planned_workout_sport_as_fallback():
    matcher = ActivityMatcher()

    activity = matcher.find_match(
        _episode(
            recommended_workout={},
            planned_workout={
                "sport": "RUN",
            },
        ),
        [
            {
                "source": "garmin",
                "source_id": "2001",
                "activity_id": "garmin:2001",
                "date": "2026-08-24T18:00:00Z",
                "sport": "BIKE",
            },
        ],
    )

    assert activity is None