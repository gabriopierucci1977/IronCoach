"""
Test goal profile intensity adaptation.
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


def test_event_goal_keeps_specificity_focus():
    workout = WorkoutAdapter().adapt(
        context=_context("EVENTO"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["goal_adjustment"]["goal_type"]
        == "EVENTO"
    )


def test_performance_goal_keeps_quality_focus():
    workout = WorkoutAdapter().adapt(
        context=_context("PERFORMANCE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        "qualitativi"
        in workout["goal_adjustment"]["focus"]
    )


def test_wellness_goal_is_more_conservative():
    workout = WorkoutAdapter().adapt(
        context=_context("BENESSERE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["goal_adjustment"]["goal_type"]
        == "BENESSERE"
    )