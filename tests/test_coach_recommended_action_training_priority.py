"""
Test training priority influence on recommended action.

Verifica che la priorità allenante
venga tradotta in un'azione operativa.
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


def test_event_priority_changes_action():
    decision = DecisionEngine().decide(
        _assessments("EVENTO")
    )

    assert (
        "specifico gara"
        in decision["recommended_action"]
    )


def test_performance_priority_changes_action():
    decision = DecisionEngine().decide(
        _assessments("PERFORMANCE")
    )

    assert (
        "qualit"
        in decision["recommended_action"]
    )


def test_wellness_priority_changes_action():
    decision = DecisionEngine().decide(
        _assessments("BENESSERE")
    )

    assert (
        "sostenibil"
        in decision["recommended_action"]
    )


def test_recovery_priority_changes_action():
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
        "recuper"
        in decision["recommended_action"]
    )