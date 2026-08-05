"""
Test training priority derived from athlete goal.
"""

from backend.engines.decision_engine import (
    DecisionEngine,
)


def _base_assessments(goal_type):
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
        "nutrition": {
            "level": "LOW",
            "reasons": [],
        },
        "load": {
            "level": "LOW",
            "reasons": [],
        },
        "adaptation": {
            "adaptation_level": "GOOD",
            "reasons": [],
        },
        "performance": {
            "trend": "IMPROVING",
            "reasons": [],
            "details": {},
        },
        "goal_profile": {
            "goal_type": goal_type,
        },
    }


def test_event_goal_has_race_specificity_priority():
    decision = DecisionEngine().decide(
        _base_assessments("EVENTO")
    )

    assert (
        decision["training_priority"]
        == "SPECIFICITA_GARA"
    )


def test_performance_goal_has_performance_priority():
    decision = DecisionEngine().decide(
        _base_assessments("PERFORMANCE")
    )

    assert (
        decision["training_priority"]
        == "SVILUPPO_PRESTAZIONE"
    )


def test_wellness_goal_has_continuity_priority():
    decision = DecisionEngine().decide(
        _base_assessments("BENESSERE")
    )

    assert (
        decision["training_priority"]
        == "CONTINUITA"
    )


def test_recovery_goal_has_restore_priority():
    assessments = _base_assessments(
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
        decision["training_priority"]
        == "RIPRISTINO"
    )