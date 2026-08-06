"""
Contratto di output della training priority nel WorkoutAdapter.
"""

import pytest

from backend.workout_adapter import WorkoutAdapter


PRIORITIES = (
    "SPECIFICITA_GARA",
    "SVILUPPO_PRESTAZIONE",
    "CONTINUITA",
    "RIPRISTINO",
)

STRATEGIES = (
    "ADAPT",
    "REDUCE_LOAD",
    "RECOVERY",
)


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


@pytest.mark.parametrize("priority", PRIORITIES)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_priority_is_preserved_in_workout_output(
    priority: str,
    strategy: str,
) -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": strategy,
            "training_priority": priority,
        },
    )

    assert workout is not None
    assert workout["strategy"] == strategy
    assert workout["training_priority"] == priority


@pytest.mark.parametrize("priority", PRIORITIES)
def test_adapt_output_contains_priority_execution_metadata(
    priority: str,
) -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": priority,
        },
    )

    assert workout["stimulus_adjustment"]
    assert workout["stimulus_adjustment"]["type"]
    assert workout["intensity"]
    assert workout["main_set"]
    assert workout["technical_focus"]
    assert workout["removed_elements"]


def test_unknown_priority_uses_standard_stimulus() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
            "training_priority": "UNKNOWN",
        },
    )

    assert workout["training_priority"] == "UNKNOWN"
    assert workout["stimulus_adjustment"]["type"] == "STANDARD"


def test_missing_priority_does_not_break_adaptation() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "ADAPT",
        },
    )

    assert workout is not None
    assert workout["training_priority"] is None
    assert workout["stimulus_adjustment"]["type"] == "STANDARD"


def test_keep_plan_without_priority_returns_none() -> None:
    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision={
            "strategy": "KEEP_PLAN",
        },
    )

    assert workout is None