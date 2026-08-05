"""
Test WorkoutAdapter goal profile propagation.
"""

from backend.workout_adapter import WorkoutAdapter


def _context():
    return {
        "training": {
            "sport": "RUN",
            "Nome seduta": "Ripetute qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
        "goal_profile": {
            "goal_type": "EVENTO",
            "primary_goal": "Preparazione Ironman",
            "race_target": "Ironman Italia 2026",
        },
    }


def test_workout_contains_goal_profile() -> None:
    decision = {
        "strategy": "ADAPT",
    }

    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision=decision,
    )

    assert (
        workout["goal_profile"]["goal_type"]
        == "EVENTO"
    )

    assert (
        workout["goal_profile"]["race_target"]
        == "Ironman Italia 2026"
    )


def test_goal_profile_fallback_from_decision_intelligence() -> None:
    context = _context()

    context.pop(
        "goal_profile"
    )

    decision = {
        "strategy": "ADAPT",
        "intelligence": {
            "goal_profile": {
                "goal_type": "PERFORMANCE",
                "primary_goal": "Migliorare FTP",
            },
        },
    }

    workout = WorkoutAdapter().adapt(
        context=context,
        decision=decision,
    )

    assert (
        workout["goal_profile"]["goal_type"]
        == "PERFORMANCE"
    )


def test_missing_goal_profile_returns_empty_profile() -> None:
    context = _context()

    context.pop(
        "goal_profile"
    )

    workout = WorkoutAdapter().adapt(
        context=context,
        decision={
            "strategy": "RECOVERY",
        },
    )

    assert (
        workout["goal_profile"]
        == {}
    )


def test_strategy_is_not_changed_by_goal_profile() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "RECOVERY",
        },
    )

    assert (
        workout["strategy"]
        == "RECOVERY"
    )


def test_keep_plan_returns_no_modified_workout() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "KEEP_PLAN",
        },
    )

    assert workout is None