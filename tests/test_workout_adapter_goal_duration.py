"""
Test goal profile duration adaptation.
"""

from backend.workout_adapter import WorkoutAdapter


def _context(goal_type):
    return {
        "training": {
            "sport": "RUN",
            "Nome seduta": "Seduta qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 100,
        },
        "goal_profile": {
            "goal_type": goal_type,
        },
    }


def test_event_goal_preserves_more_duration():
    workout = WorkoutAdapter().adapt(
        context=_context("EVENTO"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["duration_minutes"]
        == 90
    )


def test_performance_goal_preserves_quality_volume():
    workout = WorkoutAdapter().adapt(
        context=_context("PERFORMANCE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["duration_minutes"]
        == 85
    )


def test_wellness_goal_reduces_more_duration():
    workout = WorkoutAdapter().adapt(
        context=_context("BENESSERE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["duration_minutes"]
        == 70
    )


def test_unknown_goal_keeps_standard_adaptation():
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "RUN",
                "Durata minuti": 100,
            },
        },
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["duration_minutes"]
        == 80
    )