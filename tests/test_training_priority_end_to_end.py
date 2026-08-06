"""
Test end-to-end della training priority.
"""

from backend.coach_engine import CoachEngine
from backend.workout_adapter import WorkoutAdapter


def _context(goal_type: str, recovery_level: str = "LOW") -> dict:
    return {
        "athlete_profile": {
            "goal_profile": {
                "goal_type": goal_type,
            },
        },
        "recovery": {
            "level": recovery_level,
        },
        "training": {
            "sport": "RUN",
            "Nome seduta": "Ripetute qualità",
            "Tipo seduta": "Intervalli",
            "Zona prevista": "Z4",
            "Durata minuti": 60,
        },
        "nutrition": {},
        "training_history": [],
        "recovery_history": [],
        "performance_history": [],
    }


def _adapt(
    context: dict,
    decision: dict,
    strategy: str,
) -> dict:
    workout = WorkoutAdapter().adapt(
        context=context,
        decision={
            **decision,
            "strategy": strategy,
        },
    )

    assert workout is not None
    return workout


def test_event_priority_end_to_end() -> None:
    context = _context("EVENTO")
    decision = CoachEngine().evaluate(context)

    assert decision["training_priority"] == "SPECIFICITA_GARA"
    assert "Priorità allenante: Specificità gara" in decision["reason"]
    assert "specifico gara" in decision["recommended_action"]

    workout = _adapt(context, decision, "ADAPT")

    assert workout["training_priority"] == "SPECIFICITA_GARA"
    assert workout["stimulus_adjustment"]["type"] == "SPECIFICITY"


def test_performance_priority_end_to_end() -> None:
    context = _context("PERFORMANCE")
    decision = CoachEngine().evaluate(context)

    assert decision["training_priority"] == "SVILUPPO_PRESTAZIONE"
    assert "Priorità allenante: Sviluppo prestazione" in decision["reason"]
    assert "qualit" in decision["recommended_action"]

    workout = _adapt(context, decision, "ADAPT")

    assert workout["training_priority"] == "SVILUPPO_PRESTAZIONE"
    assert workout["stimulus_adjustment"]["type"] == "QUALITY"


def test_wellness_priority_end_to_end() -> None:
    context = _context("BENESSERE")
    decision = CoachEngine().evaluate(context)

    assert decision["training_priority"] == "CONTINUITA"
    assert "Priorità allenante: Continuità" in decision["reason"]
    assert "sostenibil" in decision["recommended_action"]

    workout = _adapt(context, decision, "ADAPT")

    assert workout["training_priority"] == "CONTINUITA"
    assert workout["stimulus_adjustment"]["type"] == "AEROBIC_CONTROL"
    assert "VO2" in workout["stimulus_adjustment"]["removed_elements"]


def test_recovery_priority_end_to_end() -> None:
    context = _context(
        "BENESSERE",
        recovery_level="CRITICAL",
    )
    decision = CoachEngine().evaluate(context)

    assert decision["training_priority"] == "RIPRISTINO"
    assert "Priorità allenante: Ripristino" in decision["reason"]
    assert "recuper" in decision["recommended_action"]

    workout = _adapt(context, decision, "RECOVERY")

    assert workout["training_priority"] == "RIPRISTINO"