"""
Test explanation of training priority.

Verifica che la priorità allenante
sia resa visibile nella spiegazione
della decisione.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def _assessments(goal_type):
    return {
        "recovery": {
            "level": "LOW",
            "reasons": [],
        },
        "training": {
            "level": "LOW",
            "reasons": [],
        },
        "injury": {
            "level": "LOW",
            "reasons": [],
        },
        "load": {
            "level": "LOW",
            "reasons": [],
        },
        "goal_profile": {
            "goal_type": goal_type,
        },
    }


def test_event_priority_is_explained():
    decision = DecisionEngine().decide(
        _assessments("EVENTO")
    )

    assert (
        "Priorità allenante: Specificità gara"
        in decision["reason"]
    )


def test_performance_priority_is_explained():
    decision = DecisionEngine().decide(
        _assessments("PERFORMANCE")
    )

    assert (
        "Priorità allenante: Sviluppo prestazione"
        in decision["reason"]
    )


def test_wellness_priority_is_explained():
    decision = DecisionEngine().decide(
        _assessments("BENESSERE")
    )

    assert (
        "Priorità allenante: Continuità"
        in decision["reason"]
    )


def test_recovery_priority_is_explained():
    assessments = _assessments(
        "BENESSERE"
    )

    assessments["recovery"] = {
        "level": "CRITICAL",
        "reasons": [],
    }

    decision = DecisionEngine().decide(
        assessments
    )

    assert (
        "Priorità allenante: Ripristino"
        in decision["reason"]
    )