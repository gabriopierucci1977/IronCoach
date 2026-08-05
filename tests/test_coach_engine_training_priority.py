"""
Test CoachEngine propagation of training priority.

Verifica che la priorità allenante,
derivata dal DecisionEngine,
rimanga disponibile nella decisione finale.
"""

from backend.coach_engine import CoachEngine


def _context(goal_type):
    return {
        "athlete_profile": {
            "goal_profile": {
                "goal_type": goal_type,
            }
        },
        "recovery": {},
        "training": {},
        "nutrition": {},
        "training_history": [],
        "recovery_history": [],
        "performance_history": [],
    }


def test_event_priority_is_propagated():
    decision = CoachEngine().evaluate(
        _context("EVENTO")
    )

    assert (
        decision["training_priority"]
        == "SPECIFICITA_GARA"
    )


def test_performance_priority_is_propagated():
    decision = CoachEngine().evaluate(
        _context("PERFORMANCE")
    )

    assert (
        decision["training_priority"]
        == "SVILUPPO_PRESTAZIONE"
    )


def test_wellness_priority_is_propagated():
    decision = CoachEngine().evaluate(
        _context("BENESSERE")
    )

    assert (
        decision["training_priority"]
        == "CONTINUITA"
    )


def test_recovery_priority_is_propagated():
    context = _context("BENESSERE")

    context["recovery"] = {
        "level": "CRITICAL",
    }

    decision = CoachEngine().evaluate(
        context
    )

    assert (
        decision["training_priority"]
        == "RIPRISTINO"
    )