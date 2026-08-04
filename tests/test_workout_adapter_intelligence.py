"""
Test WorkoutAdapter intelligence.

Verifica che:
- la strategia della decisione venga applicata correttamente;
- ADAPT generi una seduta ridotta ma ancora allenante;
- RECOVERY generi una seduta rigenerante;
- KEEP_PLAN non modifichi il piano;
- lo sport venga mantenuto nella proposta.
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
        }
    }


def test_adapt_strategy_generates_reduced_quality_workout() -> None:
    decision = {
        "strategy": "ADAPT",
        "risk_level": "CAUTION",
        "intelligence": {
            "performance": {
                "trend": "DECLINING",
            },
            "recovery": {
                "trend": "DECLINING",
            },
        },
    }

    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision=decision,
    )

    assert workout is not None

    assert workout[
        "strategy"
    ] == "ADAPT"

    assert workout[
        "sport_category"
    ] == "RUN"

    assert workout[
        "duration_minutes"
    ] == 48

    assert (
        "Ripetute intense"
        in workout["removed_elements"]
    )


def test_recovery_strategy_generates_easy_session() -> None:
    decision = {
        "strategy": "RECOVERY",
        "risk_level": "HIGH_ALERT",
        "intelligence": {
            "adaptation": {
                "adaptation_level": "LIMITED",
            },
        },
    }

    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision=decision,
    )

    assert workout is not None

    assert workout[
        "strategy"
    ] == "RECOVERY"

    assert workout[
        "duration_minutes"
    ] == 30

    assert workout[
        "intensity"
    ] == "Z1 molto facile"

    assert (
        "Nessun lavoro di qualità"
        in workout["notes"]
    )


def test_keep_plan_returns_no_modified_workout() -> None:
    decision = {
        "strategy": "KEEP_PLAN",
        "risk_level": "NORMAL",
    }

    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision=decision,
    )

    assert workout is None


def test_adapter_preserves_original_workout_information() -> None:
    decision = {
        "strategy": "ADAPT",
    }

    workout = WorkoutAdapter().adapt(
        context=_context(),
        decision=decision,
    )

    assert workout[
        "original_workout"
    ] == "Ripetute qualità"

    assert workout[
        "original_type"
    ] == "Intervalli"

    assert workout[
        "original_zone"
    ] == "Z4"

    assert workout[
        "original_duration_minutes"
    ] == 60