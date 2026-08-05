"""
Test propagation of training priority into WorkoutAdapter.
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
        },
    }


def test_event_training_priority_is_preserved():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "KEEP_PLAN",
            "training_priority": "SPECIFICITA_GARA",
        },
    )

    assert (
        workout["training_priority"]
        == "SPECIFICITA_GARA"
    )


def test_performance_training_priority_is_preserved():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "KEEP_PLAN",
            "training_priority": "SVILUPPO_PRESTAZIONE",
        },
    )

    assert (
        workout["training_priority"]
        == "SVILUPPO_PRESTAZIONE"
    )


def test_wellness_training_priority_is_preserved():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": "CONTINUITA",
        },
    )

    assert (
        workout["training_priority"]
        == "CONTINUITA"
    )


def test_recovery_training_priority_is_preserved():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "RECOVERY",
            "training_priority": "RIPRISTINO",
        },
    )

    assert (
        workout["training_priority"]
        == "RIPRISTINO"
    )