"""
Test training priority influence on workout stimulus.
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


def test_event_priority_preserves_specificity_stimulus():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": "SPECIFICITA_GARA",
        },
    )

    assert (
        workout["stimulus_adjustment"]["type"]
        == "SPECIFICITY"
    )


def test_performance_priority_preserves_quality_stimulus():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": "SVILUPPO_PRESTAZIONE",
        },
    )

    assert (
        workout["stimulus_adjustment"]["type"]
        == "QUALITY"
    )


def test_continuity_priority_reduces_complexity():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": "CONTINUITA",
        },
    )

    assert (
        "Sprint"
        in workout["stimulus_adjustment"]["removed_elements"]
        or
        "VO2"
        in workout["stimulus_adjustment"]["removed_elements"]
    )


def test_restore_priority_creates_recovery_stimulus():
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "RECOVERY",
            "training_priority": "RIPRISTINO",
        },
    )

    assert (
        workout["stimulus_adjustment"]["type"]
        == "RECOVERY"
    )