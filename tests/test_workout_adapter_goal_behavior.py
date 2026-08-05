"""
Test WorkoutAdapter goal based adjustment.
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
            "primary_goal": "Obiettivo test",
            "race_target": "Gara test 2026",
        },
    }


def test_event_goal_generates_specificity_adjustment():
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

    assert (
        "specificità"
        in workout["goal_adjustment"]["focus"]
    )


def test_performance_goal_generates_quality_adjustment():
    workout = WorkoutAdapter().adapt(
        context=_context("PERFORMANCE"),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["goal_adjustment"]["goal_type"]
        == "PERFORMANCE"
    )

    assert (
        "qualitativi"
        in workout["goal_adjustment"]["focus"]
    )


def test_wellness_goal_generates_continuity_adjustment():
    workout = WorkoutAdapter().adapt(
        context=_context("BENESSERE"),
        decision={
            "strategy": "RECOVERY",
        },
    )

    assert (
        workout["goal_adjustment"]["goal_type"]
        == "BENESSERE"
    )

    assert (
        "continuità"
        in workout["goal_adjustment"]["focus"]
    )


def test_missing_goal_returns_standard_adjustment():
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "RUN",
                "Durata minuti": 60,
            },
        },
        decision={
            "strategy": "ADAPT",
        },
    )

    assert (
        workout["goal_adjustment"]["goal_type"]
        == "NON DEFINITO"
    )


def test_goal_adjustment_preserves_strategy():
    workout = WorkoutAdapter().adapt(
        context=_context("EVENTO"),
        decision={
            "strategy": "RECOVERY",
        },
    )

    assert (
        workout["goal_adjustment"]["strategy"]
        == "RECOVERY"
    )