"""
Test dei campi allenamento normalizzati e del fallback raw
nel WorkoutAdapter.
"""

from backend.workout_adapter import WorkoutAdapter


def _decision():
    return {
        "strategy": "RECOVERY",
        "training_priority": "RIPRISTINO",
    }


def test_adapter_reads_normalized_training_fields() -> None:
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "RUN",
                "workout_name": "Corsa progressiva",
                "session_type": "Qualità",
                "intensity": "Z4",
                "duration_minutes": 72,
            },
        },
        decision=_decision(),
    )

    assert workout["original_workout"] == "Corsa progressiva"
    assert workout["original_type"] == "Qualità"
    assert workout["original_zone"] == "Z4"
    assert workout["planned_zone"] == "Z2"
    assert workout["original_duration_minutes"] == 72
    assert workout["duration_minutes"] == 36


def test_adapter_reads_training_fields_from_raw_fallback() -> None:
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "RUN",
                "raw": {
                    "Nome seduta": "6x1000 pista",
                    "Tipo seduta": "Intervalli",
                    "Zona prevista": "Z5",
                    "Durata minuti": "58",
                },
            },
        },
        decision=_decision(),
    )

    assert workout["original_workout"] == "6x1000 pista"
    assert workout["original_type"] == "Intervalli"
    assert workout["original_zone"] == "Z5"
    assert workout["planned_zone"] == "Z2"
    assert workout["original_duration_minutes"] == 58
    assert workout["duration_minutes"] == 29


def test_normalized_training_fields_win_over_raw_fallback() -> None:
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "BIKE",
                "workout_name": "Tempo bike",
                "session_type": "Tempo",
                "intensity": "Z3",
                "duration_minutes": 90,
                "raw": {
                    "Nome seduta": "Vecchia seduta",
                    "Tipo seduta": "Recupero",
                    "Zona prevista": "Z1",
                    "Durata minuti": "45",
                },
            },
        },
        decision={
            "strategy": "ADAPT",
            "training_priority": "SVILUPPO_PRESTAZIONE",
        },
    )

    assert workout["original_workout"] == "Tempo bike"
    assert workout["original_type"] == "Tempo"
    assert workout["original_zone"] == "Z3"
    assert workout["planned_zone"] == "Z3"
    assert workout["original_duration_minutes"] == 90
    assert workout["duration_minutes"] == 72