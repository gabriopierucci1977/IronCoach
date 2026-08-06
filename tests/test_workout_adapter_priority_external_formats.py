"""
Test dei formati esterni supportati per training_priority.
"""

import pytest

from backend.workout_adapter import WorkoutAdapter


def _context() -> dict:
    return {
        "training": {
            "sport": "RUN",
            "Nome seduta": "Seduta programmata",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
    }


@pytest.mark.parametrize(
    ("raw_priority", "expected_priority", "expected_type"),
    (
        (
            "specificità gara",
            "SPECIFICITA_GARA",
            "SPECIFICITY",
        ),
        (
            "continuità",
            "CONTINUITA",
            "AEROBIC_CONTROL",
        ),
        (
            {"value": "sviluppo prestazione"},
            "SVILUPPO_PRESTAZIONE",
            "QUALITY",
        ),
        (
            {"value": "ripristino"},
            "RIPRISTINO",
            "RECOVERY",
        ),
    ),
)
def test_external_priority_formats_are_supported(
    raw_priority,
    expected_priority: str,
    expected_type: str,
) -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": raw_priority,
        },
    )

    assert workout["training_priority"] == expected_priority
    assert workout["stimulus_adjustment"]["type"] == expected_type


@pytest.mark.parametrize(
    "empty_priority",
    (
        None,
        "",
        "   ",
        {},
        {"value": ""},
    ),
)
def test_empty_priority_uses_standard_stimulus(
    empty_priority,
) -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": empty_priority,
        },
    )

    assert workout["training_priority"] is None
    assert workout["stimulus_adjustment"]["type"] == "STANDARD"