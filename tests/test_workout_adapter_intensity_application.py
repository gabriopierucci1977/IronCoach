"""
Test application of goal based intensity adjustment.
"""

from backend.workout_adapter import WorkoutAdapter


def _context(goal_type):
    return {
        "training": {
            "sport": "RUN",
            "Nome seduta": "Ripetute qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
        "goal_profile": {
            "goal_type": goal_type,
        },
    }


def test_event_goal_preserves_planned_zone():
    workout = WorkoutAdapter().adapt(
        context=_context("EVENTO"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["planned_zone"]
        == "Z4"
    )


def test_performance_goal_preserves_quality_zone():
    workout = WorkoutAdapter().adapt(
        context=_context("PERFORMANCE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["planned_zone"]
        == "Z4"
    )


def test_wellness_goal_reduces_intensity_zone():
    workout = WorkoutAdapter().adapt(
        context=_context("BENESSERE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["planned_zone"]
        == "Z3"
    )


def test_recovery_strategy_keeps_low_intensity():
    workout = WorkoutAdapter().adapt(
        context=_context("BENESSERE"),
        decision={
            "strategy": "RECOVERY",
        },
    )

    assert (
        workout["planned_zone"]
        == "Z1"
    )