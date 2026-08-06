"""
Test di normalizzazione della training priority
nel WorkoutAdapter.
"""

import pytest

from backend.workout_adapter import WorkoutAdapter


@pytest.mark.parametrize(
    ("raw_priority", "expected_priority", "expected_type"),
    (
        (
            "specificita gara",
            "SPECIFICITA_GARA",
            "SPECIFICITY",
        ),
        (
            "specificita-gara",
            "SPECIFICITA_GARA",
            "SPECIFICITY",
        ),
        (
            "sviluppo prestazione",
            "SVILUPPO_PRESTAZIONE",
            "QUALITY",
        ),
        (
            "continuita",
            "CONTINUITA",
            "AEROBIC_CONTROL",
        ),
        (
            "ripristino",
            "RIPRISTINO",
            "RECOVERY",
        ),
    ),
)
def test_training_priority_is_normalized(
    raw_priority: str,
    expected_priority: str,
    expected_type: str,
) -> None:
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "RUN",
                "Nome seduta": "Seduta programmata",
                "Tipo seduta": "Intervalli",
                "Zona prevista": "Z4",
                "Durata minuti": 60,
            },
        },
        decision={
            "strategy": "ADAPT",
            "training_priority": raw_priority,
        },
    )

    assert workout["training_priority"] == expected_priority
    assert workout["stimulus_adjustment"]["type"] == expected_type


def test_priority_normalization_removes_extra_spaces() -> None:
    workout = WorkoutAdapter().adapt(
        context={
            "training": {
                "sport": "BIKE",
                "Nome seduta": "Seduta programmata",
                "Tipo seduta": "Intervalli",
                "Zona prevista": "Z4",
                "Durata minuti": 60,
            },
        },
        decision={
            "strategy": "ADAPT",
            "training_priority": "  sviluppo   prestazione  ",
        },
    )

    assert (
        workout["training_priority"]
        == "SVILUPPO_PRESTAZIONE"
    )
    assert (
        workout["stimulus_adjustment"]["type"]
        == "QUALITY"
    )


def test_keep_plan_returns_normalized_priority() -> None:
    workout = WorkoutAdapter().adapt(
        context={},
        decision={
            "strategy": "KEEP_PLAN",
            "training_priority": "specificita gara",
        },
    )

    assert workout == {
        "training_priority": "SPECIFICITA_GARA",
        "strategy": "KEEP_PLAN",
    }